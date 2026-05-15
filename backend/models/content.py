# backend/models/content.py
import uuid
from sqlalchemy import String, Integer, Float, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base
import enum


class ContentType(str, enum.Enum):
    movie = "movie"
    series = "series"


class Content(Base):
    __tablename__ = "content"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_slug: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_site: Mapped[str | None] = mapped_column(String(64), nullable=True)
    site_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    history: Mapped[list["WatchHistory"]] = relationship(back_populates="content", cascade="all, delete-orphan")