# backend/availability/scheduler.py
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# How many titles to preload per category on startup
# Safe for free Render tier given ~1s per scraper check
PRELOAD_LIMITS = {
    "trending": 20,
    "anime":    10,
    "kdrama":   10,
    "cdrama":   10,
    "jdrama":   10,
}


@asynccontextmanager
async def lifespan(app):
    """
    Drop-in lifespan for main.py.
    Runs preload + stale sweep on every cold start / wake-up.
    """
    asyncio.create_task(_startup())
    yield


async def _startup():
    logger.info("[scheduler] startup sequence starting")
    try:
        await _preload_all_categories()
    except Exception as e:
        logger.error(f"[scheduler] preload failed: {e}", exc_info=True)

    try:
        await _stale_sweep()
    except Exception as e:
        logger.error(f"[scheduler] stale sweep failed: {e}", exc_info=True)

    logger.info("[scheduler] startup sequence complete")


async def _preload_all_categories():
    """
    Fetches top titles from every category in parallel from TMDB,
    ingests them into the DB, then runs availability checks sequentially.
    """
    from enrichment.tmdb import get_tmdb_all_categories
    from db import AsyncSessionFactory
    from models.content import Content, ContentType
    from models.availability import ContentAvailability, AvailabilityStatus
    from availability.service import check_one
    from sqlalchemy import select

    logger.info("[preloader] fetching all categories from TMDB")
    categories = await get_tmdb_all_categories()

    # Deduplicate by tmdb_id across all categories
    seen_tmdb_ids: set[int] = set()
    to_check: list[str] = []  # content_ids that need availability check

    async with AsyncSessionFactory() as db:
        for category, items in categories.items():
            limit = PRELOAD_LIMITS.get(category, 10)
            logger.info(f"[preloader] {category}: {len(items)} from TMDB, limiting to {limit}")

            for item in items[:limit]:
                tmdb_id = item.get("tmdb_id")
                if not tmdb_id or tmdb_id in seen_tmdb_ids:
                    continue
                seen_tmdb_ids.add(tmdb_id)

                # Check if already in DB
                result = await db.execute(
                    select(Content).where(Content.tmdb_id == tmdb_id)
                )
                content = result.scalar_one_or_none()

                if not content:
                    content = Content(
                        id=str(uuid.uuid4()),
                        tmdb_id=tmdb_id,
                        content_type=ContentType(item["content_type"]),
                        title=item["title"],
                        overview=item.get("overview"),
                        poster_path=item.get("poster_path"),
                        backdrop_path=item.get("backdrop_path"),
                        release_year=item.get("release_year"),
                        rating=item.get("rating"),
                        category=item.get("category"),
                    )
                    db.add(content)
                    await db.flush()
                    logger.info(f"[preloader] ingested '{content.title}'")

                # Check if availability row exists and is already matched
                avail = await db.get(ContentAvailability, content.id)
                if avail and avail.status == AvailabilityStatus.MATCHED:
                    continue  # already good, skip

                to_check.append(content.id)

        await db.commit()

    logger.info(f"[preloader] {len(to_check)} titles need availability check")

    # Run checks sequentially — safe on free tier, ~1s each
    async with AsyncSessionFactory() as db:
        for content_id in to_check:
            try:
                await check_one(content_id, db)
            except Exception as e:
                logger.error(f"[preloader] check failed for {content_id}: {e}")

    logger.info("[preloader] done")


async def _stale_sweep():
    """Re-checks anything stale that wasn't covered by the preloader."""
    from db import AsyncSessionFactory
    from availability.driver import run_stale_sweep

    async with AsyncSessionFactory() as db:
        await run_stale_sweep(db)