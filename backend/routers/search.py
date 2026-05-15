# backend/routers/search.py
import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import get_db
from cache import cache_get, cache_set
from models.content import Content, ContentType
from models.availability import ContentAvailability, AvailabilityStatus
from models.user import User
from schemas.content import ContentOut
from dependencies import get_current_user
from enrichment.tmdb import search_tmdb
from scrapers.matcher import find_stream_source

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[ContentOut])
@limiter.limit("30/minute")
async def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100),
    page: int = Query(1, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = f"{q}:page:{page}"
    cached = await cache_get("search", cache_key)
    if cached:
        return cached

    # ── 1. Check DB — only return confirmed available content ──────────────
    result = await db.execute(
        select(Content)
        .join(ContentAvailability, Content.id == ContentAvailability.content_id)
        .where(
            Content.title.ilike(f"%{q}%"),
            ContentAvailability.status == AvailabilityStatus.MATCHED,
        )
        .order_by(
            case((func.lower(Content.title) == q.lower(), 0), else_=1),
            Content.rating.desc().nulls_last(),
            Content.tmdb_id.asc(),
        )
        .limit(20)
        .offset((page - 1) * 20)
    )
    local = result.scalars().all()

    if local:
        data = [ContentOut.model_validate(c).model_dump() for c in local]
        await cache_set("search", cache_key, data, ttl=300)
        return data

    # ── 2. Nothing matched locally — hit TMDB ─────────────────────────────
    tmdb_results = await search_tmdb(q, page=page)
    if not tmdb_results:
        return []

    # ── 3. Ingest into DB (awaited, not fire-and-forget) ──────────────────
    content_ids = await _ingest_tmdb_results(db, tmdb_results)

    # ── 4. Try to match top 5 synchronously ───────────────────────────────
    # Limit to 5 to keep response time acceptable (~1s per title)
    matched = []
    for content_id in content_ids[:5]:
        content = await db.get(Content, content_id)
        if not content:
            continue

        avail = await db.get(ContentAvailability, content_id)
        if avail and avail.status == AvailabilityStatus.MATCHED:
            matched.append(ContentOut.model_validate(content).model_dump())
            continue

        match = await find_stream_source(
            content.title,
            content.content_type.value,
            content.category,
            content.release_year,
        )

        if match:
            from datetime import datetime

            content.source_site = match["source_site"]
            content.source_slug = match["source_slug"]
            content.site_path   = match.get("site_path")

            if not avail:
                avail = ContentAvailability(content_id=content_id)
                db.add(avail)

            avail.status          = AvailabilityStatus.MATCHED
            avail.source_site     = match["source_site"]
            avail.source_slug     = match["source_slug"]
            avail.site_path       = match.get("site_path")
            avail.last_found_at   = datetime.utcnow()
            avail.last_checked_at = datetime.utcnow()
            await db.commit()

            matched.append(ContentOut.model_validate(content).model_dump())
        else:
            # Mark as not_found so retry logic picks it up later
            from datetime import datetime, timedelta
            if not avail:
                avail = ContentAvailability(content_id=content_id)
                db.add(avail)
            avail.status          = AvailabilityStatus.NOT_FOUND
            avail.last_checked_at = datetime.utcnow()
            avail.retry_after     = datetime.utcnow() + timedelta(days=1)
            await db.commit()

    if matched:
        await cache_set("search", cache_key, matched, ttl=300)
        return matched

    # ── 5. Nothing playable found — return empty, don't lie ───────────────
    return []


async def _ingest_tmdb_results(db: AsyncSession, results: list[dict]) -> list[str]:
    """
    Inserts TMDB results into the DB if they don't exist.
    Returns list of content_ids for the ingested items.
    """
    content_ids = []

    for item in results:
        tmdb_id = item.get("tmdb_id")
        if not tmdb_id:
            continue

        existing = await db.execute(
            select(Content).where(Content.tmdb_id == tmdb_id)
        )
        content = existing.scalar_one_or_none()

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

        content_ids.append(content.id)

    await db.commit()
    return content_ids