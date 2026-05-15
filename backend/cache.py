# backend/cache.py
import json
import hashlib
from typing import Any
import logging

import redis.asyncio as aioredis
from config import settings

logger = logging.getLogger(__name__)
redis = None


async def init_cache():
    global redis
    try:
        redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await redis.ping()
        logger.info("Redis connected")
    except Exception:
        logger.warning("Redis unavailable — caching disabled")
        redis = None


async def close_cache():
    global redis
    if redis:
        try:
            await redis.aclose()
        except Exception:
            pass


def _make_key(namespace: str, raw: str) -> str:
    hashed = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"nud:{namespace}:{hashed}"


async def cache_get(namespace: str, raw: str) -> Any | None:
    if not redis:
        return None
    try:
        key = _make_key(namespace, raw)
        value = await redis.get(key)
        if value:
            return json.loads(value)
    except Exception:
        pass
    return None


async def cache_set(namespace: str, raw: str, data: Any, ttl: int = 300) -> None:
    if not redis:
        return
    try:
        key = _make_key(namespace, raw)
        await redis.set(key, json.dumps(data), ex=ttl)
    except Exception:
        pass


async def cache_delete(namespace: str, raw: str) -> None:
    if not redis:
        return
    try:
        key = _make_key(namespace, raw)
        await redis.delete(key)
    except Exception:
        pass