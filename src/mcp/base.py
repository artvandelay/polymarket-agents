"""Base MCP server with generic Polymarket tools."""

from __future__ import annotations

import json
import logging
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from ..polymarket import gamma, clob
from ..polymarket.utils import safe_json

logger = logging.getLogger(__name__)


class BaseMCPServer:

    def __init__(self, name: str = "polymarket"):
        self.server = Server(name)
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            base_tools = self._base_tools()
            domain_tools = self._domain_tools()
            return base_tools + domain_tools

        @self.server.call_tool()
        async def call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[types.TextContent]:
            try:
                result = await self._dispatch(name, arguments)
                text = json.dumps(result, indent=2, default=str)
            except Exception as e:
                logger.error("Tool %s failed: %s", name, e)
                text = json.dumps({"error": str(e), "tool": name}, indent=2)
            return [types.TextContent(type="text", text=text)]

    @staticmethod
    def _base_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="get_odds",
                description=(
                    "Get current odds / implied probability for a specific market token. "
                    "Pass a clobTokenId (from get_match results). "
                    "Returns buy price, sell price, and midpoint as implied probabilities."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "token_id": {
                            "type": "string",
                            "description": "CLOB token ID from the market's clobTokenIds array.",
                        },
                    },
                    "required": ["token_id"],
                },
            ),
            types.Tool(
                name="get_orderbook",
                description=(
                    "Get full orderbook depth (all bids and asks) for a market token. "
                    "Shows where the money is sitting -- useful for understanding liquidity, "
                    "support/resistance levels, and potential slippage."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "token_id": {
                            "type": "string",
                            "description": "CLOB token ID.",
                        },
                    },
                    "required": ["token_id"],
                },
            ),
            types.Tool(
                name="get_spread",
                description=(
                    "Get the bid-ask spread for a market token. "
                    "A tight spread means high liquidity; a wide spread means "
                    "you'll pay more to enter/exit. Returns spread in absolute "
                    "and percentage terms."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "token_id": {
                            "type": "string",
                            "description": "CLOB token ID.",
                        },
                    },
                    "required": ["token_id"],
                },
            ),
            types.Tool(
                name="get_price_history",
                description=(
                    "Get historical price movement for a market token. "
                    "Shows how odds have shifted over time -- critical for "
                    "understanding market sentiment and finding value. "
                    "Returns timestamped price points."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "token_id": {
                            "type": "string",
                            "description": "CLOB token ID.",
                        },
                        "interval": {
                            "type": "string",
                            "description": "Time interval: '1m', '5m', '1h', '1d'. Default '1h'.",
                            "default": "1h",
                        },
                        "fidelity": {
                            "type": "integer",
                            "description": "Resolution in minutes. Default 60.",
                            "default": 60,
                        },
                    },
                    "required": ["token_id"],
                },
            ),
            types.Tool(
                name="search_events",
                description=(
                    "Search for events/markets by text query. "
                    "Searches across event titles and slugs. "
                    "Use this to find specific matches or topics."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query, e.g. 'afghanistan', 'bitcoin', 'election'.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results. Default 20.",
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="analyze_odds",
                description=(
                    "Analyze a betting opportunity by computing expected value. "
                    "Give your estimated probability and the current market price "
                    "to see if there's an edge worth betting on. "
                    "Also computes Kelly criterion fraction for optimal bet sizing."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "your_probability": {
                            "type": "number",
                            "description": "Your estimated probability (0-1), e.g. 0.65 means you think 65% chance.",
                        },
                        "market_price": {
                            "type": "number",
                            "description": "Current market price (0-1), e.g. 0.57 from get_odds.",
                        },
                    },
                    "required": ["your_probability", "market_price"],
                },
            ),
        ]

    def _domain_tools(self) -> list[types.Tool]:
        return []

    async def _dispatch(self, name: str, args: dict[str, Any]) -> Any:

        # --- generic Polymarket tools ---
        if name == "get_odds":
            token_id = args["token_id"]
            buy_price = await clob.get_price(token_id, "buy")
            sell_price = await clob.get_price(token_id, "sell")
            midpoint = await clob.get_midpoint(token_id)
            buy_p = float(buy_price.get("price", 0))
            sell_p = float(sell_price.get("price", 0))
            mid_p = float(midpoint.get("mid", 0))
            return {
                "token_id": token_id,
                "buy_price": buy_p,
                "sell_price": sell_p,
                "midpoint": mid_p,
                "implied_probability_buy": f"{buy_p * 100:.1f}%",
                "implied_probability_mid": f"{mid_p * 100:.1f}%",
            }

        if name == "get_orderbook":
            return await clob.get_orderbook(args["token_id"])

        if name == "get_spread":
            return await clob.get_spread(args["token_id"])

        if name == "get_price_history":
            token_id = args["token_id"]
            interval = args.get("interval", "1h")
            fidelity = args.get("fidelity", 60)
            history = await clob.get_price_history(token_id, interval, fidelity)
            return {
                "token_id": token_id,
                "interval": interval,
                "points": len(history),
                "history": history,
            }

        if name == "search_events":
            events = await gamma.search_events(args["query"], args.get("limit", 20))
            return format_events(events)

        if name == "analyze_odds":
            return clob.compute_expected_value(
                probability_estimate=args["your_probability"],
                market_price=args["market_price"],
            )

        # Fall through to domain dispatch
        return await self._dispatch_domain(name, args)

    async def _dispatch_domain(self, name: str, args: dict[str, Any]) -> Any:
        return {"error": f"Unknown tool: {name}"}

    async def run(self) -> None:
        logger.info("Starting MCP server '%s' ...", self.server.name)
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def format_events(events: list[dict]) -> list[dict]:
    results = []
    for e in events:
        markets_summary = []
        for m in e.get("markets", []):
            outcomes = safe_json(m.get("outcomes", "[]"))
            prices = safe_json(m.get("outcomePrices", "[]"))
            token_ids = safe_json(m.get("clobTokenIds", "[]"))
            odds: dict[str, dict] = {}
            for i, outcome in enumerate(outcomes):
                price = float(prices[i]) if i < len(prices) else 0
                tid = token_ids[i] if i < len(token_ids) else None
                odds[outcome] = {
                    "price": price,
                    "implied_pct": f"{price * 100:.1f}%",
                    "token_id": tid,
                }
            markets_summary.append({
                "question": m.get("question"),
                "type": m.get("sportsMarketType", "unknown"),
                "volume": f"${float(m.get('volume', 0)):,.0f}",
                "odds": odds,
            })

        results.append({
            "title": e.get("title"),
            "slug": e.get("slug"),
            "volume": (
                f"${e.get('volume', 0):,.0f}"
                if isinstance(e.get("volume"), (int, float))
                else e.get("volume")
            ),
            "liquidity": (
                f"${e.get('liquidity', 0):,.0f}"
                if isinstance(e.get("liquidity"), (int, float))
                else e.get("liquidity")
            ),
            "active": e.get("active"),
            "closed": e.get("closed"),
            "start_date": e.get("startDate") or e.get("creationDate"),
            "end_date": e.get("endDate"),
            "markets": markets_summary,
        })
    return results


def format_event_detail(event: dict) -> dict:
    formatted = format_events([event])
    if formatted:
        detail = formatted[0]
        detail["description"] = event.get("description", "")
        detail["resolution_source"] = event.get("resolutionSource", "")
        detail["volume_24h"] = event.get("volume24hr")
        detail["volume_1w"] = event.get("volume1wk")
        detail["competitive"] = event.get("competitive")
        return detail
    return {"error": "Failed to format event"}


