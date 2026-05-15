# backend/enrichment/tmdb.py
import aiohttp
import asyncio
from typing import Optional

from config import settings

TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)
MAX_RETRIES = 3

ANIME_GENRE_IDS = {16}
KDRAMA_ORIGIN_COUNTRIES = {"KR"}
CDRAMA_ORIGIN_COUNTRIES = {"CN"}
JDRAMA_ORIGIN_COUNTRIES = {"JP"}


def _detect_category(item: dict, is_movie: bool) -> str:
    genre_ids = set(item.get("genre_ids", []))
    origin    = set(item.get("origin_country", []))

    # Anime — must be animation AND Japanese origin (excludes Pixar/Disney)
    if 16 in genre_ids and "JP" in origin and not is_movie:
        return "anime"

    # Korean drama
    if origin & KDRAMA_ORIGIN_COUNTRIES and not is_movie:
        return "kdrama"

    # Chinese drama
    if origin & CDRAMA_ORIGIN_COUNTRIES and not is_movie:
        return "cdrama"

    # Japanese live-action drama (not anime)
    if "JP" in origin and 16 not in genre_ids and not is_movie:
        return "jdrama"

    if is_movie:
        return "movie"

    return "series"


async def _tmdb_get(path: str, params: dict = {}) -> dict:
    url = f"{settings.TMDB_BASE_URL}{path}"
    params = {**params, "api_key": settings.TMDB_API_KEY}

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as e:
                if e.status in (401, 404):
                    raise
                last_error = e
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
            await asyncio.sleep(2 ** attempt)
        raise last_error


def _format_poster(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return f"{settings.TMDB_IMAGE_BASE}{path}"


def _parse_year(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    try:
        return int(date_str[:4])
    except (ValueError, IndexError):
        return None


def _format_tv_item(item: dict) -> dict:
    return {
        "tmdb_id":      item.get("id"),
        "content_type": "series",
        "title":        item.get("name"),
        "overview":     item.get("overview"),
        "poster_path":  _format_poster(item.get("poster_path")),
        "backdrop_path":_format_poster(item.get("backdrop_path")),
        "release_year": _parse_year(item.get("first_air_date")),
        "rating":       item.get("vote_average"),
        "category":     _detect_category(item, is_movie=False),
        "source_site":  None,
        "source_slug":  None,
    }


async def search_tmdb(query: str, page: int = 1) -> list[dict]:
    try:
        data = await _tmdb_get("/search/multi", params={
            "query":         query,
            "page":          page,
            "include_adult": "false",
        })
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        media_type = item.get("media_type")
        if media_type not in ("movie", "tv"):
            continue
        is_movie = media_type == "movie"
        results.append({
            "tmdb_id":      item.get("id"),
            "content_type": "movie" if is_movie else "series",
            "title":        item.get("title") if is_movie else item.get("name"),
            "overview":     item.get("overview"),
            "poster_path":  _format_poster(item.get("poster_path")),
            "backdrop_path":_format_poster(item.get("backdrop_path")),
            "release_year": _parse_year(
                item.get("release_date") if is_movie else item.get("first_air_date")
            ),
            "rating":       item.get("vote_average"),
            "category":     _detect_category(item, is_movie),
            "source_site":  None,
            "source_slug":  None,
        })
    return results


async def get_tmdb_details(tmdb_id: int, content_type: str) -> Optional[dict]:
    path = f"/movie/{tmdb_id}" if content_type == "movie" else f"/tv/{tmdb_id}"
    try:
        item = await _tmdb_get(path, params={"append_to_response": "credits"})
    except Exception:
        return None

    is_movie = content_type == "movie"
    return {
        "tmdb_id":      item.get("id"),
        "content_type": content_type,
        "title":        item.get("title") if is_movie else item.get("name"),
        "overview":     item.get("overview"),
        "poster_path":  _format_poster(item.get("poster_path")),
        "backdrop_path":_format_poster(item.get("backdrop_path")),
        "release_year": _parse_year(
            item.get("release_date") if is_movie else item.get("first_air_date")
        ),
        "rating":       item.get("vote_average"),
        "category":     _detect_category(item, is_movie),
        "source_site":  None,
        "source_slug":  None,
    }


async def get_tmdb_trending(media_type: str = "all", time_window: str = "day") -> list[dict]:
    try:
        data = await _tmdb_get(f"/trending/{media_type}/{time_window}")
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        media = item.get("media_type", media_type)
        if media not in ("movie", "tv"):
            continue
        is_movie = media == "movie"
        results.append({
            "tmdb_id":      item.get("id"),
            "content_type": "movie" if is_movie else "series",
            "title":        item.get("title") if is_movie else item.get("name"),
            "overview":     item.get("overview"),
            "poster_path":  _format_poster(item.get("poster_path")),
            "backdrop_path":_format_poster(item.get("backdrop_path")),
            "release_year": _parse_year(
                item.get("release_date") if is_movie else item.get("first_air_date")
            ),
            "rating":       item.get("vote_average"),
            "category":     _detect_category(item, is_movie),
            "source_site":  None,
            "source_slug":  None,
        })
    return results


async def _discover_tv(params: dict) -> list[dict]:
    """Generic TV discover fetch — returns formatted items."""
    try:
        data = await _tmdb_get("/discover/tv", params={
            "sort_by":           "popularity.desc",
            "include_adult":     "false",
            "include_null_first_air_dates": "false",
            **params,
        })
    except Exception:
        return []

    return [_format_tv_item(item) for item in data.get("results", [])]


async def get_tmdb_anime(page: int = 1) -> list[dict]:
    """
    Anime — animation genre (16) + Japanese origin.
    Excludes western cartoons like Pixar/Disney.
    """
    return await _discover_tv({
        "with_genres":         "16",
        "with_origin_country": "JP",
        "page":                page,
    })


async def get_tmdb_kdrama(page: int = 1) -> list[dict]:
    """Korean dramas."""
    return await _discover_tv({
        "with_origin_country": "KR",
        "page":                page,
    })


async def get_tmdb_cdrama(page: int = 1) -> list[dict]:
    """Chinese dramas."""
    return await _discover_tv({
        "with_origin_country": "CN",
        "page":                page,
    })


async def get_tmdb_jdrama(page: int = 1) -> list[dict]:
    """
    Japanese live-action dramas.
    Excludes anime by filtering out animation genre (16).
    """
    return await _discover_tv({
        "with_origin_country": "JP",
        "without_genres":      "16",
        "page":                page,
    })


async def get_tmdb_all_categories() -> dict[str, list[dict]]:
    """
    Fetches all categories in parallel.
    Used by the startup preloader — one call gets everything.
    """
    trending, anime, kdrama, cdrama, jdrama = await asyncio.gather(
        get_tmdb_trending("all", "day"),
        get_tmdb_anime(),
        get_tmdb_kdrama(),
        get_tmdb_cdrama(),
        get_tmdb_jdrama(),
        return_exceptions=True,
    )

    return {
        "trending": trending if not isinstance(trending, Exception) else [],
        "anime":    anime    if not isinstance(anime,    Exception) else [],
        "kdrama":   kdrama   if not isinstance(kdrama,   Exception) else [],
        "cdrama":   cdrama   if not isinstance(cdrama,   Exception) else [],
        "jdrama":   jdrama   if not isinstance(jdrama,   Exception) else [],
    }


async def get_tmdb_seasons(tmdb_id: int) -> list[dict]:
    try:
        data = await _tmdb_get(f"/tv/{tmdb_id}")
    except Exception:
        return []

    seasons = []
    for season in data.get("seasons", []):
        if season.get("season_number", 0) == 0:
            continue
        seasons.append({
            "season_number": season.get("season_number"),
            "episode_count": season.get("episode_count"),
            "name":          season.get("name"),
            "poster_path":   _format_poster(season.get("poster_path")),
            "air_date":      season.get("air_date"),
        })
    return seasons


async def get_tmdb_episodes(tmdb_id: int, season: int) -> list[dict]:
    try:
        data = await _tmdb_get(f"/tv/{tmdb_id}/season/{season}")
    except Exception:
        return []

    episodes = []
    for ep in data.get("episodes", []):
        episodes.append({
            "episode_number": ep.get("episode_number"),
            "season_number":  ep.get("season_number"),
            "name":           ep.get("name"),
            "overview":       ep.get("overview"),
            "still_path":     _format_poster(ep.get("still_path")),
            "air_date":       ep.get("air_date"),
            "runtime":        ep.get("runtime"),
        })
    return episodes