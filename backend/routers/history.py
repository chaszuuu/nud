# backend/routers/history.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import get_db
from models.history import WatchHistory
from models.user import User
from schemas.history import HistoryCreate, HistoryOut
from dependencies import get_current_user

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/", response_model=list[HistoryOut])
@limiter.limit("30/minute")
async def get_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WatchHistory)
        .where(WatchHistory.user_id == current_user.id)
        .order_by(WatchHistory.watched_at.desc())
        .limit(100)
    )
    return result.scalars().all()


@router.post("/", response_model=HistoryOut, status_code=201)
@limiter.limit("60/minute")
async def upsert_history(
    request: Request,
    payload: HistoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # upsert — update if exists, insert if not
    result = await db.execute(
        select(WatchHistory).where(
            and_(
                WatchHistory.user_id == current_user.id,
                WatchHistory.content_id == payload.content_id,
                WatchHistory.episode == payload.episode,
                WatchHistory.season == payload.season,
            )
        )
    )
    entry = result.scalar_one_or_none()

    if entry:
        entry.progress = payload.progress
        entry.completed = payload.completed
    else:
        entry = WatchHistory(
            user_id=current_user.id,
            content_id=payload.content_id,
            episode=payload.episode,
            season=payload.season,
            progress=payload.progress,
            completed=payload.completed,
        )
        db.add(entry)

    await db.flush()
    return entry


@router.delete("/{history_id}", status_code=204)
@limiter.limit("20/minute")
async def delete_history(
    request: Request,
    history_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WatchHistory).where(
            and_(
                WatchHistory.id == history_id,
                WatchHistory.user_id == current_user.id,  # users can only delete their own
            )
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    await db.delete(entry)