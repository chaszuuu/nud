# backend/scrapers/jobs.py
"""
In-memory job store for async stream resolution.

Each job goes through these states:
  pending  → scraper not started yet
  running  → Playwright is working
  ready    → stream_url + subtitles available
  failed   → resolution failed, error message available

When Redis is available, swap this module's storage for a Redis-backed
implementation without touching any other file.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    READY   = "ready"
    FAILED  = "failed"


@dataclass
class StreamJob:
    job_id:     str
    content_id: str
    season:     Optional[int]
    episode:    Optional[int]
    status:     JobStatus = JobStatus.PENDING
    stream_url: Optional[str] = None
    subtitles:  list[dict]    = field(default_factory=list)
    error:      Optional[str] = None
    message:    str           = "Finding stream source..."


# Global in-memory store  {job_id: StreamJob}
_jobs: dict[str, StreamJob] = {}


def create_job(content_id: str, season: Optional[int], episode: Optional[int]) -> StreamJob:
    job_id = str(uuid.uuid4())
    job = StreamJob(job_id=job_id, content_id=content_id, season=season, episode=episode)
    _jobs[job_id] = job
    logger.info(f"[jobs] created job {job_id} for content={content_id} s={season} e={episode}")
    return job


def get_job(job_id: str) -> Optional[StreamJob]:
    return _jobs.get(job_id)


def cleanup_job(job_id: str):
    _jobs.pop(job_id, None)