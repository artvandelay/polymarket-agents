"""Gamma API client for event/market discovery."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .utils import API_TIMEOUT

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

_client = httpx.AsyncClient(timeout=API_TIMEOUT)

async def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{GAMMA_BASE}{path}"
    resp = await _client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


async def list_sports() -> list[dict]:
    return await _get("/sports")


async def get_market_types() -> dict:
    return await _get("/sports/market-types")


async def list_teams(sport: str | None = None) -> list[dict]:
    params: dict[str, Any] = {}
    if sport:
        params["sport"] = sport
    return await _get("/teams", params=params or None)


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
    results = await _get("/events", params={"slug": slug})
    if isinstance(results, list) and results:
        return results[0]
    if isinstance(results, dict):
        return results
    return None


async def get_market_by_slug(slug: str) -> dict | None:
    results = await _get("/markets", params={"slug": slug})
    if isinstance(results, list) and results:
        return results[0]
    if isinstance(results, dict):
        return results
    return None


async def search_events(query: str, limit: int = 20) -> list[dict]:
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
