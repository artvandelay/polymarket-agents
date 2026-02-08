"""
Gamma API client for Polymarket event/market discovery.

Domain-agnostic — no cricket, crypto, or politics knowledge here.

Endpoints used (all public, no auth):
  GET /sports                    -- list sports leagues with series_id
  GET /sports/market-types       -- valid sports market types
  GET /teams                     -- list teams for a sport
  GET /events?series_id=X&...    -- events (matches) for a league
  GET /events?slug=X             -- single event by slug
  GET /markets?slug=X            -- single market by slug
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
TIMEOUT = 30.0


_client: httpx.AsyncClient | None = None

async def _get_client() -> httpx.AsyncClient:
    """Get or create shared HTTP client."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=TIMEOUT)
    return _client

async def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Issue a GET to the Gamma API and return parsed JSON."""
    client = await _get_client()
    url = f"{GAMMA_BASE}{path}"
    logger.debug("GET %s params=%s", url, params)
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


# ── Sports / league discovery ────────────────────────────────────────

async def list_sports() -> list[dict]:
    """Return every sport/league Polymarket supports, with series_id."""
    return await _get("/sports")


async def get_market_types() -> dict:
    """Return valid sports market types (moneyline, cricket_toss_winner, etc.)."""
    return await _get("/sports/market-types")


async def list_teams(sport: str | None = None) -> list[dict]:
    """List teams.  Optionally filter by sport abbreviation."""
    params: dict[str, Any] = {}
    if sport:
        params["sport"] = sport
    return await _get("/teams", params=params or None)


# ── Events (matches / markets) ──────────────────────────────────────

async def list_events(
    *,
    series_id: str | None = None,
    tag_id: str | None = None,
    active: bool = True,
    closed: bool = False,
    limit: int = 50,
    offset: int = 0,
    order: str = "startDate",
    ascending: bool = True,
) -> list[dict]:
    """
    List events from Gamma API with flexible filtering.

    For sports matches, the docs recommend:
      series_id  = from /sports (e.g. 10528 for crint)
      tag_id     = 100639 for game-level bets (not futures)
    """
    params: dict[str, Any] = {
        "active": str(active).lower(),
        "closed": str(closed).lower(),
        "limit": limit,
        "offset": offset,
        "order": order,
        "ascending": str(ascending).lower(),
    }
    if series_id:
        params["series_id"] = series_id
    if tag_id:
        params["tag_id"] = tag_id
    return await _get("/events", params=params)


async def get_event_by_slug(slug: str) -> dict | None:
    """Fetch a single event by its URL slug, including sub-markets."""
    results = await _get("/events", params={"slug": slug})
    if isinstance(results, list) and results:
        return results[0]
    if isinstance(results, dict):
        return results
    return None


async def get_market_by_slug(slug: str) -> dict | None:
    """Fetch a single market by slug (includes clobTokenIds)."""
    results = await _get("/markets", params={"slug": slug})
    if isinstance(results, list) and results:
        return results[0]
    if isinstance(results, dict):
        return results
    return None


# ── Search ───────────────────────────────────────────────────────────

async def search_events(query: str, limit: int = 20) -> list[dict]:
    """
    Text search across events/markets on Gamma.
    Falls back to fetching recent events and filtering client-side
    if the search endpoint doesn't return useful results.
    """
    try:
        result = await _get("/events", params={
            "slug_contains": query.lower().replace(" ", "-"),
            "active": "true",
            "closed": "false",
            "limit": limit,
        })
        if result:
            return result if isinstance(result, list) else [result]
    except httpx.HTTPStatusError:
        pass

    # Fallback: broad event search with client-side filter
    all_events = await list_events(limit=200, order="id", ascending=False)
    q = query.lower()
    return [
        e for e in all_events
        if q in e.get("title", "").lower()
        or q in e.get("slug", "").lower()
        or q in e.get("description", "").lower()
    ][:limit]
