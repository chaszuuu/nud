# backend/availability/driver.py
import os
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# "inline" = free Render tier  |  "arq" = paid/scaled
DRIVER = os.getenv("AVAILABILITY_DRIVER", "inline")


async def enqueue_check(content_id: str):
    """
    Single entry point for triggering an availability check.
    Callers never know which driver is active.
    """
    if DRIVER == "arq":
        await _enqueue_arq(content_id)
    else:
        task = asyncio.create_task(_safe_check(content_id))
        task.add_done_callback(
            lambda t: logger.error(
                f"[driver] inline check failed for {content_id}: {t.exception()}"
            ) if t.exception() else None
        )


async def run_stale_sweep(db: AsyncSession):
    """
    Called on startup (free tier) or by ARQ cron (paid tier).
    Same function either way — driver only changes HOW items are dispatched.
    """
    from availability.service import get_stale, reset_stuck_checking

    await reset_stuck_checking(db)

    limit = 20 if DRIVER == "inline" else 200
    stale = await get_stale(db, limit=limit)

    if not stale:
        logger.info("[driver] sweep: nothing stale")
        return

    logger.info(f"[driver] sweep: {len(stale)} items via driver={DRIVER}")

    if DRIVER == "arq":
        for row in stale:
            await _enqueue_arq(row.content_id)
    else:
        # Sequential on free tier — don't hammer the scraper
        for row in stale:
            await _safe_check(row.content_id)


async def _safe_check(content_id: str):
    from db import AsyncSessionFactory
    from availability.service import check_one
    try:
        async with AsyncSessionFactory() as db:
            await check_one(content_id, db)
    except Exception as e:
        logger.error(f"[driver] check failed for {content_id}: {e}", exc_info=True)


async def _enqueue_arq(content_id: str):
    """Only active when AVAILABILITY_DRIVER=arq."""
    from workers.arq_pool import enqueue
    await enqueue("check_availability_task", content_id)