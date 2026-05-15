# backend/schemas/content.py
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from models.content import ContentType
import re


class ContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    tmdb_id: int
    content_type: ContentType
    title: str
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_year: Optional[int] = None
    rating: Optional[float] = None
    source_site: Optional[str] = None
    category: Optional[str] = None


class ContentSearch(BaseModel):
    q: str
    page: int = 1

    @field_validator("q")
    @classmethod
    def query_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Query cannot be empty")
        if len(v) > 100:
            raise ValueError("Query too long")
        if re.search(r"<[^>]+>", v):
            raise ValueError("Invalid characters in query")
        return v

    @field_validator("page")
    @classmethod
    def page_valid(cls, v: int) -> int:
        if v < 1 or v > 500:
            raise ValueError("Page must be between 1 and 500")
        return v


class StreamRequest(BaseModel):
    content_id: str
    episode: Optional[int] = None
    season: Optional[int] = None

    @field_validator("content_id")
    @classmethod
    def content_id_valid(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-f0-9-]{36}$", v):
            raise ValueError("Invalid content ID")
        return v