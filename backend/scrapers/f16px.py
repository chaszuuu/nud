# backend/scrapers/f16px.py
"""
Resolver for any embed player that internally uses the f16px/Byse player.
Returns both the m3u8 stream URL and subtitle tracks.
Cookies are stored in Redis instead of a local file.
"""

import asyncio
import json
import logging
import re
import time
import concurrent.futures
from typing import Optional
from dataclasses import dataclass, field

import aiohttp
import redis

from config import settings

logger = logging.getLogger(__name__)

TIMEOUT_S   = 45
COOKIE_KEY  = "f16px:cookies"        # Redis key
WARMUP_URL  = "https://f16px.com/"
COOKIE_TTL  = 60 * 60 * 24 * 7      # 7 days in seconds


@dataclass
class StreamResult:
    url: str
    subtitles: list[dict] = field(default_factory=list)


# ── Redis cookie helpers ───────────────────────────────────────────────────── #

def _redis_client() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def _load_cookies() -> list[dict]:
    """Load cookies from Redis."""
    try:
        r = _redis_client()
        data = r.get(COOKIE_KEY)
        if data:
            cookies = json.loads(data)
            if isinstance(cookies, list) and cookies:
                logger.debug(f"[f16px] loaded {len(cookies)} cookies from Redis")
                return cookies
    except Exception as e:
        logger.debug(f"[f16px] Redis cookie load failed: {e}")
    return []


def _save_cookies(cookies: list[dict]):
    """Persist cookies to Redis, deduplicating by name + domain."""
    try:
        seen = {}
        for c in cookies:
            domain = (c.get("domain") or "").lstrip(".")
            key = (c.get("name"), domain)
            seen[key] = c
        deduped = list(seen.values())

        r = _redis_client()
        r.setex(COOKIE_KEY, COOKIE_TTL, json.dumps(deduped))
        logger.debug(f"[f16px] saved {len(deduped)} cookies to Redis")
    except Exception as e:
        logger.debug(f"[f16px] Redis cookie save failed: {e}")


def _has_cookies() -> bool:
    """Check if we have cookies stored in Redis."""
    try:
        r = _redis_client()
        return r.exists(COOKIE_KEY) == 1
    except Exception as e:
        logger.debug(f"[f16px] Redis exists check failed: {e}")
        return False


# ── Browser helpers ────────────────────────────────────────────────────────── #

def _make_browser_args():
    return [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]


def _make_ua():
    return (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.5 Mobile/15E148 Safari/604.1"
    )


def _warmup_sync():
    """
    Runs in its own thread + event loop.
    Visits f16px.com to acquire byse_viewer_id / byse_device_id cookies.
    Fully isolated — browser closed before resolve starts.
    """
    async def _do():
        from playwright.async_api import async_playwright
        logger.info("[f16px] starting warmup browser")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=_make_browser_args())
            context = await browser.new_context(user_agent=_make_ua())
            page    = await context.new_page()
            try:
                await page.goto(WARMUP_URL, wait_until="domcontentloaded", timeout=20_000)
                await asyncio.sleep(4)
                cookies = await context.cookies()
                _save_cookies(cookies)
                logger.info(f"[f16px] warmup done — {len(cookies)} cookies saved to Redis")
            except Exception as e:
                logger.warning(f"[f16px] warmup failed: {e}")
            finally:
                await page.close()
                await context.close()
                await browser.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_do())
    finally:
        loop.close()


def _resolve_sync(embed_url: str) -> Optional[StreamResult]:
    """
    Runs in its own thread + event loop.
    Fresh browser every call — no shared Playwright state with warmup.
    """
    async def _do() -> Optional[StreamResult]:
        from playwright.async_api import async_playwright

        saved_cookies = _load_cookies()
        loop          = asyncio.get_event_loop()
        m3u8_future: asyncio.Future = loop.create_future()
        subtitles: list[dict] = []

        async def fetch_subtitles_from_url(sub_url: str, label: str):
            try:
                headers = {
                    "Referer": "https://f16px.com/",
                    "Origin":  "https://f16px.com",
                    "Accept":  "application/json, */*",
                }
                async with aiohttp.ClientSession() as s:
                    async with s.get(sub_url, headers=headers) as r:
                        text = await r.text()
                        if not text or not text.strip().startswith("["):
                            logger.debug(f"[f16px] subtitle not JSON ({label}): {text[:80]!r}")
                            return
                        data = json.loads(text)
                        if isinstance(data, list) and data:
                            subtitles.extend(data)
                            logger.info(f"[f16px] fetched {len(data)} subtitle(s) from {label}")
            except Exception as e:
                logger.debug(f"[f16px] subtitle fetch failed ({label}): {e}")

        async def handle_request(request):
            url = request.url
            if ".m3u8" in url and not m3u8_future.done():
                if "master" in url or "index" not in url:
                    logger.info(f"[f16px] intercepted m3u8: {url[:80]}…")
                    m3u8_future.set_result(url)

        async def handle_response(response):
            url = response.url
            if ".m3u8" in url and not m3u8_future.done():
                if "master" in url or "index" not in url:
                    logger.info(f"[f16px] intercepted m3u8 (response): {url[:80]}…")
                    m3u8_future.set_result(url)

            if "qqqcdn.cloud/subtitles" in url and "token" in url:
                try:
                    data = await response.json()
                    if isinstance(data, list) and data:
                        logger.info(f"[f16px] found {len(data)} subtitle track(s)")
                        subtitles.clear()
                        subtitles.extend(data)
                except Exception as e:
                    logger.debug(f"[f16px] subtitle parse error: {e}")

            if "f16px.com/e/" in url and "sub.info" in url and not subtitles:
                sub_match = re.search(r'sub\.info=([^&\s]+)', url)
                if sub_match:
                    sub_url = sub_match.group(1)
                    logger.info(f"[f16px] found sub.info: {sub_url[:80]}")
                    await fetch_subtitles_from_url(sub_url, "sub.info (request)")

        result: Optional[StreamResult] = None
        logger.info(f"[f16px] resolving: {embed_url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=_make_browser_args())
            context = await browser.new_context(
                user_agent=_make_ua(),
                extra_http_headers={"Referer": "https://movies2watch.biz/"},
            )
            if saved_cookies:
                try:
                    await context.add_cookies(saved_cookies)
                    logger.debug("[f16px] restored cookies into context")
                except Exception as e:
                    logger.debug(f"[f16px] cookie restore failed: {e}")

            page = await context.new_page()
            page.on("request",  handle_request)
            page.on("response", handle_response)

            try:
                await page.goto(embed_url, wait_until="domcontentloaded", timeout=TIMEOUT_S * 1000)

                if not subtitles:
                    sub_match = re.search(r'sub\.info=([^&\s]+)', embed_url)
                    if sub_match:
                        await fetch_subtitles_from_url(sub_match.group(1), "sub.info (embed_url)")

                m3u8_url = await asyncio.wait_for(
                    asyncio.shield(m3u8_future),
                    timeout=TIMEOUT_S,
                )
                if m3u8_url:
                    await asyncio.sleep(3)
                    fresh = await context.cookies()
                    if fresh:
                        _save_cookies(fresh)
                    result = StreamResult(url=m3u8_url, subtitles=subtitles)

            except asyncio.TimeoutError:
                logger.warning(f"[f16px] timed out for {embed_url}")
                try:
                    fresh = await context.cookies()
                    if fresh:
                        _save_cookies(fresh)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[f16px] error: {e}", exc_info=True)
            finally:
                await page.close()
                await context.close()
                await browser.close()

        return result

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_do())
    finally:
        loop.close()


class F16pxResolver:

    @classmethod
    async def resolve_once(cls, embed_url: str) -> Optional[StreamResult]:
        """
        Entry point. Runs everything in thread pool workers so uvicorn's
        event loop is never touched by Playwright.

        - If no cookies in Redis, warmup runs first in its own thread.
        - Resolve always runs in a fresh thread with a fresh browser.
        """
        loop = asyncio.get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            if not _has_cookies():
                logger.info("[f16px] no cookies in Redis — running warmup first")
                await loop.run_in_executor(pool, _warmup_sync)
                time.sleep(1)

            return await loop.run_in_executor(pool, _resolve_sync, embed_url)