# backend/models/history.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base


class WatchHistory(Base):
    __tablename__ = "watch_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content.id", ondelete="CASCADE"), nullable=False, index=True
    )
    episode: Mapped[int | None] = mapped_column(Integer, nullable=True)   # null for movies
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)           # seconds watched
    completed: Mapped[bool] = mapped_column(default=False)
    watched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="history")
    content: Mapped["Content"] = relationship(back_populates="history")