# backend/models/availability.py
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AvailabilityStatus(str, enum.Enum):
    PENDING   = "pending"    # never attempted
    CHECKING  = "checking"   # task currently in flight
    MATCHED   = "matched"    # confirmed available on scraper
    NOT_FOUND = "not_found"  # tried, not there yet — will retry
    LOST      = "lost"       # was matched, now gone — will retry


class ContentAvailability(Base):
    __tablename__ = "content_availability"

    content_id: Mapped[str] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_site:           Mapped[Optional[str]]              = mapped_column(nullable=True)
    source_slug:           Mapped[Optional[str]]              = mapped_column(nullable=True)
    site_path:             Mapped[Optional[str]]              = mapped_column(nullable=True)
    status:                Mapped[AvailabilityStatus]         = mapped_column(default=AvailabilityStatus.PENDING, index=True)
    last_checked_at:       Mapped[Optional[datetime]]         = mapped_column(nullable=True)
    last_found_at:         Mapped[Optional[datetime]]         = mapped_column(nullable=True)
    check_attempts:        Mapped[int]                        = mapped_column(Integer, default=0)
    consecutive_failures:  Mapped[int]                        = mapped_column(Integer, default=0)
    retry_after:           Mapped[Optional[datetime]]         = mapped_column(nullable=True)

    __table_args__ = (
        # Fast lookup for stale sweep query
        Index("ix_avail_status_retry", "status", "retry_after"),
    )