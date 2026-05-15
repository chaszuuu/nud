# backend/scrapers/movies2watch.py
import re
import asyncio
import logging
from typing import Optional
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://movies2watch.biz"

_M3U8_BLOCKLIST_PATTERNS = [
    r"example\.com",
    r"test\.m3u8",
    r"sample\.m3u8",
    r"placeholder",
]


def _extract_numeric_id(slug: str) -> Optional[str]:
    m = re.search(r"-(\d{4,6})$", slug)
    if not m:
        logger.warning(f"[movies2watch] could not extract numeric ID from slug '{slug}'")
        return None
    return m.group(1)


def _unpack_js(packed: str) -> Optional[str]:
    try:
        m = re.search(
            r"'([^']+)'\s*,\s*(\d+)\s*,\s*\d+\s*,\s*'([^']*)'\s*\.split\(",
            packed,
        )
        if not m:
            return None
        encoded, base_str, words_str = m.groups()
        base = int(base_str)
        words = words_str.split("|")
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

        def _decode(word: str) -> str:
            val = 0
            for ch in word:
                if ch not in chars:
                    return word
                val = val * base + chars.index(ch)
            return words[val] if 0 <= val < len(words) and words[val] else word

        return re.sub(r'\b\w+\b', lambda mo: _decode(mo.group(0)), encoded)
    except Exception:
        return None


def _fix_embed_url(url: str) -> str:
    return url


def _extract_year(block: str) -> Optional[int]:
    """Extract a 4-digit year from an HTML block, e.g. a search result item."""
    m = re.search(r'\b(19\d{2}|20\d{2})\b', block)
    if m:
        return int(m.group(1))
    return None


class Movies2WatchScraper(BaseScraper):

    # ------------------------------------------------------------------ #
    #  Search — /livesearch?q= endpoint                                   #
    # ------------------------------------------------------------------ #

    async def search(self, query: str) -> list[dict]:
        try:
            html = await self._get(
                f"{BASE_URL}/livesearch",
                params={"q": query},
                headers={
                    "Referer": f"{BASE_URL}/home",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                },
            )
        except Exception as e:
            logger.error(f"[movies2watch] livesearch failed: {e}", exc_info=True)
            return []

        if not html or not html.strip():
            return []

        results = []
        seen: set[str] = set()

        for m in re.finditer(
            r'<a[^>]+class=["\']item["\'][^>]+href=["\']https?://movies2watch\.biz/(movie|series|kdrama|anime)/([^/"]+)/["\'][^>]*>'
            r'(.*?)'
            r'</a>',
            html, re.DOTALL,
        ):
            ctype_raw, slug, block = m.groups()
            slug = slug.strip()

            # Extract title from block
            title_m = re.search(
                r'<div[^>]+class=["\']title["\'][^>]*>\s*([^<]+?)\s*</div>',
                block,
            )
            if not title_m:
                continue
            title = self._clean_title(title_m.group(1))
            if slug in seen or not title:
                continue
            seen.add(slug)

            # Extract year from the block if present
            release_year = _extract_year(block)

            results.append(_make_result(ctype_raw, slug, title, release_year))

        logger.info(f"[movies2watch] livesearch '{query}' → {len(results)} results")
        return results[:20]

    # ------------------------------------------------------------------ #
    #  Core: fetch page → pl_url → server list                           #
    # ------------------------------------------------------------------ #

    async def _get_server_list(self, page_url: str) -> Optional[str]:
        html = await self._fetch_page(page_url)
        if not html:
            logger.warning(f"[movies2watch] no HTML for {page_url}")
            return None

        pl_match = re.search(r"const\s+pl_url\s*=\s*['\"]([^'\"]+)['\"]", html)
        if not pl_match:
            logger.warning(f"[movies2watch] no pl_url in {page_url}")
            return None

        pl_url = pl_match.group(1)
        logger.info(f"[movies2watch] fetching pl_url: {pl_url[:80]}…")

        server_html = await self._fetch_page(pl_url, referer=page_url)
        if not server_html:
            logger.warning("[movies2watch] no response from pl_url")
            return None

        return server_html

    def _get_embed_urls_ranked(self, server_html: str) -> list[tuple[str, str]]:
        servers = {}
        for m in re.finditer(
            r'data-srv=["\']([^"\']+)["\'][^>]+data-id=["\']([^"\']+)["\']'
            r'|data-id=["\']([^"\']+)["\'][^>]+data-srv=["\']([^"\']+)["\']',
            server_html,
        ):
            if m.group(1):
                servers[m.group(1)] = m.group(2)
            else:
                servers[m.group(4)] = m.group(3)

        logger.info(f"[movies2watch] available servers: {list(servers.keys())}")

        ranked = []
        for preferred in ("UpCloud", "Vidfast", "Videasy", "Vidsrc", "Vidking"):
            if preferred in servers:
                ranked.append((preferred, servers[preferred]))

        for name, url in servers.items():
            if not any(name == r[0] for r in ranked):
                ranked.append((name, url))

        return ranked

    async def _fetch_page(self, url: str, referer: str = f"{BASE_URL}/home") -> Optional[str]:
        try:
            return await self._get(url, headers={"Referer": referer})
        except Exception:
            try:
                return await self._get_with_cloudscraper(url, headers={"Referer": referer})
            except Exception:
                return None

    # ------------------------------------------------------------------ #
    #  Stream resolution                                                   #
    # ------------------------------------------------------------------ #

    async def _resolve_embed(self, embed_url: str) -> Optional[dict]:
        embed_url = _fix_embed_url(embed_url)
        from scrapers.f16px import F16pxResolver

        for attempt in range(2):
            try:
                result = await F16pxResolver.resolve_once(embed_url)
                if result:
                    return {
                        "stream_url": result.url,
                        "subtitles": result.subtitles,
                    }
                logger.info(f"[movies2watch] attempt {attempt + 1} returned None")
            except Exception as e:
                logger.error(f"[movies2watch] attempt {attempt + 1} failed: {e}")

        return None

    async def _resolve_with_fallback(self, server_html: str) -> Optional[dict]:
        servers = self._get_embed_urls_ranked(server_html)
        for name, embed_url in servers:
            logger.info(f"[movies2watch] trying server: {name} → {embed_url}")
            result = await self._resolve_embed(embed_url)
            if result:
                logger.info(f"[movies2watch] server {name} succeeded")
                return result
            logger.warning(f"[movies2watch] server {name} failed, trying next")
        return None

    async def _resolve_movie(self, slug: str, site_path: str = "movie") -> Optional[dict]:
        page_url = f"{BASE_URL}/{site_path}/{slug}/"
        server_html = await self._get_server_list(page_url)
        if not server_html:
            return None
        return await self._resolve_with_fallback(server_html)

    async def _resolve_series(self, slug: str, season: int, episode: int, site_path: str = "series") -> Optional[dict]:
        page_url = f"{BASE_URL}/{site_path}/{slug}/{season}-{episode}/"
        server_html = await self._get_server_list(page_url)
        if not server_html:
            return None
        return await self._resolve_with_fallback(server_html)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def get_stream_url(
        self,
        slug: str,
        episode: int = None,
        season: int = None,
        site_path: str = None,
    ) -> Optional[str]:
        """Legacy method — returns only the stream URL string."""
        result = await self.get_stream(slug, episode=episode, season=season, site_path=site_path)
        return result["stream_url"] if result else None

    async def get_stream(
        self,
        slug: str,
        episode: int = None,
        season: int = None,
        site_path: str = None,
    ) -> Optional[dict]:
        if not site_path:
            site_path = _infer_site_path(slug)

        is_series = bool(episode and season)
        logger.info(
            f"[movies2watch] get_stream slug='{slug}' site_path='{site_path}' "
            f"is_series={is_series} s={season} e={episode}"
        )
        if is_series:
            return await self._resolve_series(slug, season, episode, site_path)
        else:
            return await self._resolve_movie(slug, site_path)


# ------------------------------------------------------------------ #
#  Module-level helpers                                               #
# ------------------------------------------------------------------ #

def _make_result(ctype_raw: str, slug: str, title: str, release_year: Optional[int] = None) -> dict:
    if ctype_raw == "movie":
        content_type = "movie"
    else:
        content_type = "series"

    return {
        "title": title,
        "slug": slug,
        "source_site": "movies2watch",
        "content_type": content_type,
        "site_path": ctype_raw,
        "release_year": release_year,   # ← used by matcher for year-based disambiguation
    }


_KDRAMA_SLUG_HINTS = re.compile(r"-(kdrama|k-drama)\b", re.IGNORECASE)
_ANIME_SLUG_HINTS  = re.compile(r"-(anime)\b", re.IGNORECASE)


def _infer_site_path(slug: str) -> str:
    if _KDRAMA_SLUG_HINTS.search(slug):
        return "kdrama"
    if _ANIME_SLUG_HINTS.search(slug):
        return "anime"
    return "series"


def _find_m3u8(text: str) -> Optional[str]:
    normalized = text.replace('\\"', '"').replace("\\/", "/")
    candidates = re.findall(
        r'https?://[^\s"\'<>\\,\)]+\.m3u8(?:[^\s"\'<>\\,\)]*)?',
        normalized,
    )
    for url in candidates:
        url = url.rstrip(".,;)")
        if any(re.search(p, url, re.IGNORECASE) for p in _M3U8_BLOCKLIST_PATTERNS):
            continue
        return url
    return None