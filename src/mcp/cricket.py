"""
Cricket-specific MCP server.

Extends BaseMCPServer with 4 cricket discovery tools:
  - list_cricket_leagues
  - list_cricket_matches
  - get_match
  - get_market_types
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import mcp.types as types

from .base import BaseMCPServer, format_events, format_event_detail
from ..polymarket import gamma

logger = logging.getLogger(__name__)

# Keywords used to filter /sports for cricket leagues
_CRICKET_KEYWORDS = {"cri", "t20", "ipl", "bbl", "bpl", "sa20", "ilt20", "wpl"}


class CricketMCPServer(BaseMCPServer):
    """MCP server for Polymarket cricket market research."""

    def __init__(self) -> None:
        super().__init__(name="polymarket-cricket")

    # ── Domain tools ─────────────────────────────────────────────────

    def _domain_tools(self) -> list[types.Tool]:
        return [
            types.Tool(
                name="list_cricket_leagues",
                description=(
                    "List all cricket leagues/series available on Polymarket. "
                    "Returns league name, sport code, series_id (needed for match queries), "
                    "and resolution source."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="list_cricket_matches",
                description=(
                    "List active/upcoming cricket matches on Polymarket. "
                    "Optionally filter by series_id (from list_cricket_leagues). "
                    "Returns match title, slug, volume, odds for each match. "
                    "Set include_closed=true to also see finished matches."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "series_id": {
                            "type": "string",
                            "description": (
                                "Series ID from list_cricket_leagues "
                                "(e.g. '10528' for crint). Leave empty for all cricket."
                            ),
                        },
                        "include_closed": {
                            "type": "boolean",
                            "description": "Include closed/resolved matches. Default false.",
                            "default": False,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max matches to return. Default 30.",
                            "default": 30,
                        },
                    },
                },
            ),
            types.Tool(
                name="get_match",
                description=(
                    "Get full details for a specific cricket match by its event slug. "
                    "Returns all sub-markets (moneyline, toss winner, completed match, etc.) "
                    "with current odds, volume, and token IDs needed for price/orderbook queries. "
                    "The slug is found in the Polymarket URL: polymarket.com/event/<slug>"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "slug": {
                            "type": "string",
                            "description": "Event slug, e.g. 'crint-afg-nzl-2026-02-08'",
                        },
                    },
                    "required": ["slug"],
                },
            ),
            types.Tool(
                name="get_market_types",
                description=(
                    "List all valid sports market types on Polymarket. "
                    "Includes cricket-specific types like cricket_toss_winner, "
                    "cricket_completed_match, cricket_most_sixes, etc. "
                    "Useful for understanding what you can bet on."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    # ── Domain dispatch ──────────────────────────────────────────────

    async def _dispatch_domain(self, name: str, args: dict[str, Any]) -> Any:
        if name == "list_cricket_leagues":
            return await _list_cricket_leagues()

        if name == "list_cricket_matches":
            return await _list_cricket_matches(
                series_id=args.get("series_id"),
                include_closed=args.get("include_closed", False),
                limit=args.get("limit", 30),
            )

        if name == "get_match":
            event = await gamma.get_event_by_slug(args["slug"])
            if not event:
                return {"error": f"No event found for slug: {args['slug']}"}
            return format_event_detail(event)

        if name == "get_market_types":
            data = await gamma.get_market_types()
            all_types = data.get("marketTypes", []) if isinstance(data, dict) else data
            cricket_types = (
                [t for t in all_types if "cricket" in t.lower()]
                if isinstance(all_types, list)
                else []
            )
            return {"all_types": all_types, "cricket_types": cricket_types}

        return {"error": f"Unknown tool: {name}"}


# ── Cricket-specific helpers ─────────────────────────────────────────

async def _list_cricket_leagues() -> list[dict]:
    """Filter /sports to only cricket-related leagues."""
    all_sports = await gamma.list_sports()
    results = []
    for s in all_sports:
        sport = s.get("sport", "").lower()
        if any(kw in sport for kw in _CRICKET_KEYWORDS):
            results.append({
                "sport": s.get("sport"),
                "series_id": s.get("series"),
                "resolution": s.get("resolution"),
                "image": s.get("image"),
            })
    return results


async def _list_cricket_matches(
    series_id: str | None = None,
    include_closed: bool = False,
    limit: int = 30,
) -> list[dict]:
    """List cricket matches, auto-discovering leagues if no series_id given."""
    if series_id:
        matches = await gamma.list_events(
            series_id=series_id,
            tag_id="100639",
            active=True,
            closed=include_closed,
            limit=limit,
        )
        return format_events(matches)

    # Auto-discover all cricket leagues
    leagues = await _list_cricket_leagues()
    all_matches: list[dict] = []
    for league in leagues:
        sid = league.get("series_id")
        if not sid:
            continue
        try:
            matches = await gamma.list_events(
                series_id=sid,
                tag_id="100639",
                active=True,
                closed=include_closed,
                limit=limit,
            )
            all_matches.extend(matches)
        except Exception:
            logger.debug("No matches for series %s", sid)
    return format_events(all_matches)


# ── Entry point ──────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    server = CricketMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
