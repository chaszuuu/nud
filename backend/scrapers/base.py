# backend/scrapers/base.py
import aiohttp
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
import re
from urllib.parse import quote
from config import settings


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

MAX_RETRIES = 2
TIMEOUT = aiohttp.ClientTimeout(total=8, connect=3)


class BaseScraper(ABC):

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=HEADERS,
                timeout=TIMEOUT,
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _proxy_url(self, url: str) -> str:
        """Route URL through Cloudflare Worker if configured."""
        worker = getattr(settings, "CF_WORKER_URL", None)
        if worker:
            return f"{worker}?url={quote(url, safe='')}"
        return url

    async def _get_with_cloudscraper(self, url: str, headers: dict = {}) -> str:
        """Fallback for Cloudflare-protected sites — runs in executor to avoid blocking."""
        import cloudscraper
        loop = asyncio.get_event_loop()
        merged_headers = {**HEADERS, **headers}

        def _fetch():
            scraper = cloudscraper.create_scraper()
            try:
                response = scraper.get(url, headers=merged_headers)
                response.raise_for_status()
                return response.text
            finally:
                scraper.close()

        return await loop.run_in_executor(None, _fetch)

    async def _get(self, url: str, **kwargs) -> str:
        self._validate_url(url)
        session = await self._get_session()
        last_error = None

        proxied = self._proxy_url(url)

        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(proxied, **kwargs) as resp:
                    resp.raise_for_status()
                    return await resp.text()
            except aiohttp.ClientResponseError as e:
                if e.status == 521:
                    # Cloudflare block — try cloudscraper
                    try:
                        return await self._get_with_cloudscraper(
                            url,
                            headers=kwargs.get("headers", {})
                        )
                    except Exception as cs_err:
                        last_error = cs_err
                        break
                if e.status in (403, 404, 410):
                    raise
                last_error = e
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e

            await asyncio.sleep(0.5 * (2 ** attempt))

        raise last_error

    async def _get_json(self, url: str, **kwargs) -> dict:
        self._validate_url(url)
        session = await self._get_session()
        last_error = None

        proxied = self._proxy_url(url)

        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(proxied, **kwargs) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as e:
                if e.status == 521:
                    try:
                        import json
                        text = await self._get_with_cloudscraper(
                            url,
                            headers=kwargs.get("headers", {})
                        )
                        return json.loads(text)
                    except Exception as cs_err:
                        last_error = cs_err
                        break
                if e.status in (403, 404, 410):
                    raise
                last_error = e
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e

            await asyncio.sleep(0.5 * (2 ** attempt))

        raise last_error

    def _validate_url(self, url: str):
        blocked = [
            r"localhost", r"127\.", r"0\.0\.0\.0",
            r"10\.", r"172\.(1[6-9]|2[0-9]|3[01])\.",
            r"192\.168\.", r"169\.254\.",
            r"::1", r"fc00:", r"fe80:",
        ]
        for pattern in blocked:
            if re.search(pattern, url, re.IGNORECASE):
                raise ValueError(f"Blocked URL: {url}")

    def _clean_title(self, title: str) -> str:
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(r"[^\w\s\-:.,!?'\"()]", "", title)
        return title

    @abstractmethod
    async def search(self, query: str) -> list[dict]:
        pass

    @abstractmethod
    async def get_stream_url(self, slug: str, episode: int = None, season: int = None) -> Optional[str]:
        pass