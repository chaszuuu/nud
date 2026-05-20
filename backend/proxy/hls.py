# backend/proxy/hls.py
import re
import logging
import aiohttp
import asyncio
from urllib.parse import urlparse, urljoin, quote
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

TIMEOUT = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
CHUNK_SIZE = 1024 * 512  # 512 KB

ALLOWED_EXTENSIONS = {".m3u8", ".ts", ".key", ".aac", ".mp4", ".vtt", ".webvtt"}

# Domains that movies2watch.biz is known to serve streams from.
# Extend this list as you discover new CDN hostnames in stream URLs.
CDN_WHITELIST = [
    "netmagcdn.com",
    "rapid-cloud.co",
    "megacloud.tv",
    "megacloud.store",
    "movies2watch.biz",
    "sprintcdn.r66nv9ed.com",
    "f16px.com",
    "0123movie.space",
    "qqqcdn.cloud",
]

SAFE_RESPONSE_HEADERS = {
    "Access-Control-Allow-Origin": settings.CORS_ORIGINS[0],
    "Access-Control-Allow-Headers": "Range, Content-Type",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
}

FORWARD_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.5 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en-GB;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
    "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"iOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "priority": "u=1, i",
}

CDN_REFERERS: dict[str, str] = {
    "netmagcdn":    "https://rapid-cloud.co/",
    "rapid-cloud":  "https://rapid-cloud.co/",
    "megacloud":    "https://megacloud.tv/",
    "movies2watch": "https://movies2watch.biz/",
    "sprintcdn":    "https://f16px.com/",
    "f16px":        "https://f16px.com/",
    "0123movie":    "https://movies2watch.biz/",
    "qqqcdn":       "https://f16px.com/",

}

_session: aiohttp.ClientSession = None


async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(
            limit=100,
            ttl_dns_cache=300,
            keepalive_timeout=60,
        )
        _session = aiohttp.ClientSession(timeout=TIMEOUT, connector=connector)
    return _session


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()


def _get_referer(netloc: str, fallback: str) -> tuple[str, str]:
    for key, ref in CDN_REFERERS.items():
        if key in netloc:
            return ref, ref.rstrip("/")
    return fallback, fallback.rstrip("/")


def _validate_stream_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")

    for cdn in CDN_WHITELIST:
        if cdn in parsed.netloc:
            return url

    blocked = [
        r"localhost", r"127\.", r"0\.0\.0\.0",
        r"10\.", r"172\.(1[6-9]|2[0-9]|3[01])\.",
        r"192\.168\.", r"169\.254\.",
        r"::1", r"fc00:", r"fe80:",
        r"metadata\.google", r"169\.254\.169\.254",
    ]
    for pattern in blocked:
        if re.search(pattern, parsed.netloc, re.IGNORECASE):
            raise HTTPException(status_code=400, detail="Blocked URL")

    path = parsed.path.lower()
    if not any(path.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Invalid stream URL")

    return url


def _rewrite_m3u8(content: str, base_url: str, proxy_base: str) -> str:
    lines = content.splitlines()
    rewritten = []

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith("#EXT"):
            if 'URI="' in stripped:
                def replace_uri(m):
                    uri = m.group(1)
                    abs_url = uri if uri.startswith("http") else urljoin(base_url, uri)
                    return f'URI="{proxy_base}?url={quote(abs_url, safe="")}"'
                stripped = re.sub(r'URI="([^"]+)"', replace_uri, stripped)
            rewritten.append(stripped)
            continue

        abs_url = stripped if stripped.startswith("http") else urljoin(base_url, stripped)
        rewritten.append(f"{proxy_base}?url={quote(abs_url, safe='')}")

    return "\n".join(rewritten)


@router.get("/hls")
@limiter.limit("120/minute")
async def proxy_hls(request: Request, url: str = Query(...)):
    url = _validate_stream_url(url)
    parsed = urlparse(url)
    base_url = (
        f"{parsed.scheme}://{parsed.netloc}"
        f"{'/'.join(parsed.path.split('/')[:-1])}/"
    )
    proxy_base = str(request.url_for("proxy_hls"))

    fallback_referer = f"{parsed.scheme}://{parsed.netloc}/"
    referer, origin = _get_referer(parsed.netloc, fallback_referer)

    req_headers = {**FORWARD_REQUEST_HEADERS}
    if "range" in request.headers:
        req_headers["Range"] = request.headers["range"]
    if "if-none-match" in request.headers:
        req_headers["If-None-Match"] = request.headers["if-none-match"]
    if "if-modified-since" in request.headers:
        req_headers["If-Modified-Since"] = request.headers["if-modified-since"]
    req_headers["Referer"] = referer
    req_headers["Origin"] = origin

    try:
        session = await get_session()
        resp = await session.get(url, headers=req_headers)

        if resp.status not in (200, 206, 304):
            body = await resp.text()
            logger.error(f"[proxy] CDN {resp.status} for {url} | body={body[:300]}")
            resp.release()
            raise HTTPException(status_code=502, detail="Stream source error")

        if resp.status == 304:
            resp.release()
            return Response(
                status_code=304,
                headers={**SAFE_RESPONSE_HEADERS, "Cache-Control": "public, max-age=7200"},
            )

        content_type = resp.headers.get("Content-Type", "")
        is_m3u8 = "mpegurl" in content_type.lower() or url.endswith(".m3u8")

        if is_m3u8:
            raw = await resp.text()
            resp.release()
            rewritten = _rewrite_m3u8(raw, base_url, proxy_base)
            return Response(
                content=rewritten,
                media_type="application/vnd.apple.mpegurl",
                headers={**SAFE_RESPONSE_HEADERS, "Cache-Control": "no-store"},
            )

        async def stream_chunks():
            try:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    yield chunk
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
                return
            finally:
                resp.release()

        response_headers = {**SAFE_RESPONSE_HEADERS, "Cache-Control": "public, max-age=7200"}
        for h in ("Content-Range", "Content-Length", "ETag", "Last-Modified"):
            if resp.headers.get(h):
                response_headers[h] = resp.headers[h]

        return StreamingResponse(
            stream_chunks(),
            status_code=resp.status,
            media_type=content_type or "video/mp2t",
            headers=response_headers,
        )

    except HTTPException:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"[proxy] failed to fetch {url}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=502, detail="Failed to reach stream source")
    except Exception as e:
        logger.error(f"[proxy] unexpected error for {url}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Proxy error")
