# backend/routers/content.py
import logging
import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address
from urllib.parse import quote

from db import get_db
from cache import cache_get, cache_set
from models.content import Content, ContentType
from models.availability import ContentAvailability, AvailabilityStatus
from models.user import User
from schemas.content import ContentOut, StreamRequest
from dependencies import get_current_user
from enrichment.tmdb import get_tmdb_seasons, get_tmdb_episodes, get_tmdb_trending
from scrapers.movies2watch import Movies2WatchScraper
from scrapers.jobs import JobStatus, create_job, get_job
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

SCRAPERS = {
    "movies2watch": Movies2WatchScraper,
}


def _stream_url(raw_url: str) -> str:
    proxy_path = f"/proxy/hls?url={quote(raw_url, safe='')}"
    if settings.BACKEND_URL:
        return f"{settings.BACKEND_URL.rstrip('/')}{proxy_path}"
    return proxy_path


# ──────────────────────────────────────────────────────────────────────────── #
#  Trending — only returns MATCHED content                                     #
# ──────────────────────────────────────────────────────────────────────────── #

@router.get("/trending", response_model=list[ContentOut])
@limiter.limit("60/minute")
async def get_trending(
    request: Request,
    media_type: str = Query("all", pattern="^(all|movie|tv)$"),
    time_window: str = Query("day", pattern="^(day|week)$"),
    category: str = Query(None),  # filter by: anime, kdrama, cdrama, jdrama, movie, series
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"{media_type}:{time_window}:{category or 'all'}"
    cached = await cache_get("trending", cache_key)
    if cached:
        return cached

    # Only serve content that is confirmed available on the scraper
    query = (
        select(Content)
        .join(ContentAvailability, Content.id == ContentAvailability.content_id)
        .where(ContentAvailability.status == AvailabilityStatus.MATCHED)
        .order_by(Content.rating.desc().nulls_last())
        .limit(20)
    )

    if category:
        query = query.where(Content.category == category)

    result = await db.execute(query)
    contents = result.scalars().all()

    if not contents:
        # DB is cold — trigger preloader in background and return empty
        # User will see content after next startup / next request once preloader runs
        asyncio.create_task(_trigger_preload())
        return []

    data = [ContentOut.model_validate(c).model_dump() for c in contents]
    await cache_set("trending", cache_key, data, ttl=3600)
    return data


async def _trigger_preload():
    """Background preload trigger when DB is cold."""
    try:
        from availability.scheduler import _preload_all_categories
        await _preload_all_categories()
    except Exception as e:
        logger.error(f"[content] background preload failed: {e}")


# ──────────────────────────────────────────────────────────────────────────── #
#  Stream — background job pattern                                             #
# ──────────────────────────────────────────────────────────────────────────── #

async def _resolve_stream_job(job_id: str, content: Content):
    job = get_job(job_id)
    if not job:
        return

    cache_key = f"{job.content_id}:s{job.season}:e{job.episode}"
    cached = await cache_get("stream", cache_key)
    if cached:
        job.status     = JobStatus.READY
        job.stream_url = cached["stream_url"]
        job.subtitles  = cached.get("subtitles", [])
        job.message    = "Stream ready"
        logger.info(f"[jobs] {job_id} served from cache")
        return

    job.status  = JobStatus.RUNNING
    job.message = "Launching player..."

    if content.source_site not in SCRAPERS:
        job.status = JobStatus.FAILED
        job.error  = "No stream source available"
        return

    scraper = SCRAPERS[content.source_site]()
    try:
        job.message   = "Finding stream source..."
        stream_result = await scraper.get_stream(
            slug=content.source_slug,
            episode=job.episode,
            season=job.season,
            site_path=getattr(content, "site_path", None),
        )

        if not stream_result or not stream_result.get("stream_url"):
            job.status = JobStatus.FAILED
            job.error  = "Stream not found"
            return

        proxied_url = _stream_url(stream_result["stream_url"])
        subtitles   = stream_result.get("subtitles", [])

        job.status     = JobStatus.READY
        job.stream_url = proxied_url
        job.subtitles  = subtitles
        job.message    = "Stream ready"

        await cache_set("stream", cache_key, {
            "stream_url": proxied_url,
            "subtitles":  subtitles,
        }, ttl=3600)

        logger.info(f"[jobs] {job_id} ready: {proxied_url[:80]}...")

    except Exception as e:
        logger.error(f"[jobs] {job_id} failed: {e}", exc_info=True)
        job.status = JobStatus.FAILED
        job.error  = "Failed to resolve stream"
    finally:
        await scraper.close()


@router.post("/stream/start", response_model=dict)
@limiter.limit("20/minute")
async def start_stream(
    request: Request,
    payload: StreamRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Content).where(Content.id == payload.content_id))
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check availability table first
    avail = await db.get(ContentAvailability, content.id)

    if not avail or avail.status != AvailabilityStatus.MATCHED:
        # Not confirmed available — try on-demand match
        from scrapers.matcher import find_stream_source
        logger.info(f"[stream] on-demand match for '{content.title}'")
        try:
            match = await asyncio.wait_for(
                find_stream_source(
                    content.title,
                    content.content_type.value,
                    content.category,
                    content.release_year,
                ),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            match = None

        if match:
            content.source_site = match["source_site"]
            content.source_slug = match["source_slug"]
            content.site_path   = match.get("site_path")

            # Update availability table
            if not avail:
                avail = ContentAvailability(content_id=content.id)
                db.add(avail)
            from datetime import datetime
            avail.status        = AvailabilityStatus.MATCHED
            avail.source_site   = match["source_site"]
            avail.source_slug   = match["source_slug"]
            avail.site_path     = match.get("site_path")
            avail.last_found_at = datetime.utcnow()
            avail.last_checked_at = datetime.utcnow()

            await db.commit()
        else:
            raise HTTPException(status_code=404, detail="No stream source available")

    job = create_job(payload.content_id, payload.season, payload.episode)
    asyncio.create_task(_resolve_stream_job(job.job_id, content))

    return {"job_id": job.job_id, "status": job.status, "message": job.message}


@router.get("/stream/status/{job_id}", response_model=dict)
@limiter.limit("120/minute")
async def stream_status(
    request: Request,
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id":  job.job_id,
        "status":  job.status,
        "message": job.message,
    }

    if job.status == JobStatus.READY:
        response["stream_url"] = job.stream_url
        response["subtitles"]  = job.subtitles

    if job.status == JobStatus.FAILED:
        response["error"] = job.error

    return response


# ──────────────────────────────────────────────────────────────────────────── #
#  Content detail / seasons / episodes                                         #
# ──────────────────────────────────────────────────────────────────────────── #

@router.get("/{content_id}", response_model=ContentOut)
@limiter.limit("60/minute")
async def get_content(
    request: Request,
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cached = await cache_get("content", content_id)
    if cached:
        return cached

    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    data = ContentOut.model_validate(content).model_dump()
    await cache_set("content", content_id, data, ttl=3600)
    return data


@router.get("/{content_id}/seasons", response_model=list[dict])
@limiter.limit("60/minute")
async def get_seasons(
    request: Request,
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cached = await cache_get("seasons", content_id)
    if cached:
        return cached

    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if content.content_type.value != "series":
        raise HTTPException(status_code=400, detail="Content is not a series")

    seasons = await get_tmdb_seasons(content.tmdb_id)
    await cache_set("seasons", content_id, seasons, ttl=3600)
    return seasons


@router.get("/{content_id}/episodes", response_model=list[dict])
@limiter.limit("60/minute")
async def get_episodes(
    request: Request,
    content_id: str,
    season: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = f"{content_id}:s{season}"
    cached = await cache_get("episodes", cache_key)
    if cached:
        return cached

    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if content.content_type.value != "series":
        raise HTTPException(status_code=400, detail="Content is not a series")

    episodes = await get_tmdb_episodes(content.tmdb_id, season)
    await cache_set("episodes", cache_key, episodes, ttl=3600)
    return episodes


# ──────────────────────────────────────────────────────────────────────────── #
#  Admin — observability                                                       #
# ──────────────────────────────────────────────────────────────────────────── #

@router.get("/admin/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from availability.service import get_stats
    from scrapers.matcher import find_stream_source
    from datetime import datetime

    stats = await get_stats(db)

    # Live scraper health check
    scraper_ok = False
    scraper_ms = None
    try:
        import time
        t = time.time()
        test = await find_stream_source("Inception", "movie", "movie", 2010)
        scraper_ms = round((time.time() - t) * 1000)
        scraper_ok = test is not None
    except Exception:
        pass

    return {
        "scraper_healthy":  scraper_ok,
        "scraper_latency_ms": scraper_ms,
        "availability":     stats,
        "timestamp":        datetime.utcnow().isoformat(),
    }