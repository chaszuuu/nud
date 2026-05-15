# backend/scrapers/matcher.py
import asyncio
import logging
import re
from difflib import SequenceMatcher
from scrapers.movies2watch import Movies2WatchScraper

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.88


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower().strip())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _score_result(r: dict, title: str, release_year: int | None) -> float:
    score = _similarity(r.get("title", ""), title)

    if release_year and r.get("release_year"):
        diff = abs(r["release_year"] - release_year)
        if diff == 0:
            score += 0.05        # exact year match — boost
        elif diff <= 1:
            pass                 # one year off — neutral
        else:
            score -= 0.15        # wrong era — penalize hard enough to flip winner

    return score


def _make_queries(title: str) -> list[str]:
    base = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip()
    queries = [base]

    short = re.split(r"[:\-–]", base)[0].strip()
    if short and short != base:
        queries.append(short)

    words = [w for w in short.split() if w.lower() not in ("the", "a", "an")]
    if len(words) >= 2:
        stub = " ".join(words[:2])
        if stub not in queries:
            queries.append(stub)

    return queries


async def _try_scraper(
    scraper,
    queries: list[str],
    title: str,
    content_type: str,
    release_year: int | None = None,
) -> dict | None:
    name = scraper.__class__.__name__
    try:
        for query in queries:
            results = await scraper.search(query)
            logger.info(f"[{name}] query='{query}' → {len(results)} results")

            best = None
            best_score = 0.0

            for r in results:
                r_title = r.get("title", "")
                r_type = r.get("content_type")

                if r_type and content_type and r_type != content_type:
                    logger.debug(
                        f"  [{name}] type mismatch: expected {content_type!r}, "
                        f"got {r_type!r} for '{r_title}' — skipping"
                    )
                    continue

                score = _score_result(r, title, release_year)

                logger.debug(
                    f"  [{name}] '{r_title}' year={r.get('release_year')} "
                    f"type={r_type!r} score={score:.2f}"
                )

                if score >= MATCH_THRESHOLD and score > best_score:
                    best_score = score
                    best = r

            if best:
                logger.info(
                    f"[{name}] matched '{best['title']}' "
                    f"score={best_score:.2f} query='{query}'"
                )
                return {
                    "source_site": best["source_site"],
                    "source_slug": best["slug"],
                    "site_path": best.get("site_path", "series"),
                    "score": best_score,
                }

            logger.info(
                f"[{name}] no match above threshold {MATCH_THRESHOLD} "
                f"for query='{query}'"
            )

    except Exception as e:
        logger.error(f"[{name}] error searching '{title}': {e}", exc_info=True)
    finally:
        await scraper.close()

    return None


async def find_stream_source(
    title: str,
    content_type: str,
    category: str = None,
    release_year: int | None = None,
) -> dict | None:
    logger.info(
        f"[matcher] find_stream_source title='{title}' "
        f"content_type={content_type!r} category={category!r} "
        f"release_year={release_year!r}"
    )

    queries = _make_queries(title)
    logger.debug(f"[matcher] query ladder: {queries}")

    result = await _try_scraper(
        Movies2WatchScraper(), queries, title, content_type, release_year
    )

    logger.info(f"[matcher] result for '{title}': {result}")
    return result