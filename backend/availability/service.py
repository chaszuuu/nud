# backend/availability/service.py
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func

from models.availability import ContentAvailability, AvailabilityStatus
from models.content import Content
from scrapers.matcher import find_stream_source

logger = logging.getLogger(__name__)

REVALIDATE_MATCHED_AFTER_HOURS = 24
MAX_BACKOFF_DAYS = 7
MIN_FAILURES_TO_LOSE = 3  # require 3 consecutive misses before MATCHED → LOST


async def check_one(content_id: str, db: AsyncSession) -> ContentAvailability:
    """
    Core unit of work. Checks a single content item against the scraper
    and updates its availability row.
    Called by any driver — inline, ARQ, or otherwise.
    """
    content = await db.get(Content, content_id)
    if not content:
        logger.warning(f"[availability] content {content_id} not found")
        return None

    avail = await _get_or_create(db, content_id)
    prev_status = avail.status

    avail.status = AvailabilityStatus.CHECKING
    await db.commit()

    try:
        match = await find_stream_source(
            content.title,
            content.content_type.value,
            content.category,
            content.release_year,
        )
    except Exception as e:
        logger.error(f"[availability] scraper error for '{content.title}': {e}")
        # Scraper error ≠ not found — restore previous status, retry later
        avail.status = prev_status if prev_status != AvailabilityStatus.CHECKING else AvailabilityStatus.PENDING
        avail.retry_after = datetime.utcnow() + timedelta(hours=1)
        await db.commit()
        return avail

    now = datetime.utcnow()
    avail.last_checked_at = now
    avail.check_attempts += 1

    if match:
        avail.status             = AvailabilityStatus.MATCHED
        avail.source_site        = match["source_site"]
        avail.source_slug        = match["source_slug"]
        avail.site_path          = match.get("site_path")
        avail.last_found_at      = now
        avail.retry_after        = None
        avail.consecutive_failures = 0

        # Keep Content model in sync so stream endpoint works without a join
        content.source_site = match["source_site"]
        content.source_slug = match["source_slug"]
        content.site_path   = match.get("site_path")

    else:
        avail.consecutive_failures = (avail.consecutive_failures or 0) + 1

        was_matched = avail.last_found_at is not None

        # Don't flip MATCHED → LOST on a single scraper blip
        # Require MIN_FAILURES_TO_LOSE consecutive misses
        if was_matched and avail.consecutive_failures < MIN_FAILURES_TO_LOSE:
            logger.info(
                f"[availability] '{content.title}' miss "
                f"{avail.consecutive_failures}/{MIN_FAILURES_TO_LOSE} — staying MATCHED"
            )
            avail.status = AvailabilityStatus.MATCHED
        else:
            avail.status = (
                AvailabilityStatus.LOST
                if was_matched
                else AvailabilityStatus.NOT_FOUND
            )
            backoff = min(2 ** avail.check_attempts, MAX_BACKOFF_DAYS)
            avail.retry_after = now + timedelta(days=backoff)

            if avail.status == AvailabilityStatus.LOST:
                # Clear from Content model so stream endpoint stops serving it
                content.source_slug = None
                content.source_site = None
                content.site_path   = None

    await db.commit()
    logger.info(
        f"[availability] '{content.title}' "
        f"{prev_status} → {avail.status} "
        f"(failures={avail.consecutive_failures})"
    )
    return avail


async def get_stale(db: AsyncSession, limit: int = 20) -> list[ContentAvailability]:
    """
    Returns content that needs checking:
    - Never checked (PENDING)
    - NOT_FOUND or LOST whose retry window has passed
    - MATCHED but not revalidated in REVALIDATE_MATCHED_AFTER_HOURS
    """
    now = datetime.utcnow()
    result = await db.execute(
        select(ContentAvailability)
        .where(
            or_(
                ContentAvailability.status == AvailabilityStatus.PENDING,
                and_(
                    ContentAvailability.status.in_([
                        AvailabilityStatus.NOT_FOUND,
                        AvailabilityStatus.LOST,
                    ]),
                    ContentAvailability.retry_after <= now,
                ),
                and_(
                    ContentAvailability.status == AvailabilityStatus.MATCHED,
                    ContentAvailability.last_checked_at <= now - timedelta(
                        hours=REVALIDATE_MATCHED_AFTER_HOURS
                    ),
                ),
            )
        )
        .limit(limit)
    )
    return result.scalars().all()


async def reset_stuck_checking(db: AsyncSession):
    """
    Safety net — anything stuck in CHECKING for 10+ minutes
    gets reset to PENDING so it's retried next sweep.
    """
    stuck_before = datetime.utcnow() - timedelta(minutes=10)
    result = await db.execute(
        select(ContentAvailability)
        .where(
            and_(
                ContentAvailability.status == AvailabilityStatus.CHECKING,
                ContentAvailability.last_checked_at <= stuck_before,
            )
        )
    )
    rows = result.scalars().all()
    for row in rows:
        row.status = AvailabilityStatus.PENDING
    if rows:
        await db.commit()
        logger.info(f"[availability] reset {len(rows)} stuck CHECKING rows")


async def get_stats(db: AsyncSession) -> dict:
    """Observability — status counts at a glance."""
    result = await db.execute(
        select(
            ContentAvailability.status,
            func.count().label("count"),
        )
        .group_by(ContentAvailability.status)
    )
    return {row.status: row.count for row in result.all()}


async def _get_or_create(db: AsyncSession, content_id: str) -> ContentAvailability:
    avail = await db.get(ContentAvailability, content_id)
    if not avail:
        avail = ContentAvailability(content_id=content_id)
        db.add(avail)
        await db.flush()
    return avail