# backend/schemas/history.py
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


class HistoryCreate(BaseModel):
    content_id: str
    episode: Optional[int] = None
    season: Optional[int] = None
    progress: float = 0.0
    completed: bool = False

    @field_validator("progress")
    @classmethod
    def progress_valid(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Progress cannot be negative")
        if v > 86400:  # max 24 hours in seconds
            raise ValueError("Progress value out of range")
        return v

    @field_validator("content_id")
    @classmethod
    def content_id_valid(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-f0-9-]{36}$", v):
            raise ValueError("Invalid content ID")
        return v


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content_id: str
    episode: Optional[int] = None
    season: Optional[int] = None
    progress: float
    completed: bool
    watched_at: datetime