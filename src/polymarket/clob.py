"""
CLOB API client for Polymarket pricing and orderbook data.

Domain-agnostic — works with any Polymarket token ID.

Endpoints used (all public, no auth):
  GET /price?token_id=X&side=buy       -- current price for a token
  GET /midpoint?token_id=X             -- midpoint between best bid/ask
  GET /book?token_id=X                 -- full orderbook (bids + asks)
  GET /spread?token_id=X               -- bid-ask spread
  GET /prices-history?market=X&...     -- historical OHLC price data
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CLOB_BASE = "https://clob.polymarket.com"
TIMEOUT = 30.0


_client: httpx.AsyncClient | None = None

async def _get_client() -> httpx.AsyncClient:
    """Get or create shared HTTP client."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=TIMEOUT)
    return _client

async def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Issue a GET to the CLOB API and return parsed JSON."""
    client = await _get_client()
    url = f"{CLOB_BASE}{path}"
    logger.debug("GET %s params=%s", url, params)
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


# ── Pricing ──────────────────────────────────────────────────────────

async def get_price(token_id: str, side: str = "buy") -> dict:
    """
    Get current market price for a token.

    Args:
        token_id: The CLOB token ID (from market's clobTokenIds)
        side: 'buy' or 'sell'

    Returns:
        {"price": "0.65"}
    """
    return await _get("/price", params={"token_id": token_id, "side": side})


async def get_midpoint(token_id: str) -> dict:
    """
    Get midpoint price (average of best bid and best ask).

    Returns:
        {"mid": "0.645"}
    """
    return await _get("/midpoint", params={"token_id": token_id})


async def get_prices(token_ids: list[str], side: str = "buy") -> list[dict]:
    """Get prices for multiple tokens at once."""
    import asyncio
    
    async def fetch_price(tid: str) -> dict:
        try:
            p = await get_price(tid, side)
            return {"token_id": tid, **p}
        except httpx.HTTPStatusError as e:
            return {"token_id": tid, "error": str(e)}
    
    return await asyncio.gather(*[fetch_price(tid) for tid in token_ids])


# ── Orderbook ────────────────────────────────────────────────────────

async def get_orderbook(token_id: str) -> dict:
    """
    Get full orderbook for a token (all bids and asks).

    Returns:
        {
            "market": "0x...",
            "asset_id": "TOKEN_ID",
            "bids": [{"price": "0.64", "size": "500"}, ...],
            "asks": [{"price": "0.66", "size": "300"}, ...]
        }
    """
    return await _get("/book", params={"token_id": token_id})


async def get_spread(token_id: str) -> dict:
    """
    Get bid-ask spread for a token.

    Returns:
        {"spread": "0.02"}  or computes from orderbook
    """
    try:
        return await _get("/spread", params={"token_id": token_id})
    except httpx.HTTPStatusError:
        # Compute spread from orderbook as fallback
        book = await get_orderbook(token_id)
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        if bids and asks:
            best_bid = float(bids[0]["price"])
            best_ask = float(asks[0]["price"])
            spread = best_ask - best_bid
            return {
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": round(spread, 4),
                "spread_pct": round(spread / best_ask * 100, 2) if best_ask else 0,
            }
        return {"error": "No bids or asks available"}


# ── Historical prices ────────────────────────────────────────────────

async def get_price_history(
    token_id: str,
    interval: str = "1h",
    fidelity: int = 60,
) -> list[dict]:
    """
    Get historical price data for a token.

    Args:
        token_id: CLOB token ID
        interval: Time interval ('1m', '5m', '1h', '1d')
        fidelity: Number of data points (resolution in minutes)

    Returns:
        List of {"t": timestamp, "p": price} objects
    """
    try:
        result = await _get("/prices-history", params={
            "market": token_id,
            "interval": interval,
            "fidelity": fidelity,
        })
        if isinstance(result, dict) and "history" in result:
            return result["history"]
        return result if isinstance(result, list) else []
    except httpx.HTTPStatusError as e:
        logger.warning("Price history failed: %s", e)
        return []


# ── Helpers ──────────────────────────────────────────────────────────

def compute_implied_probability(price: float) -> float:
    """Convert a market price (0-1) to implied probability percentage."""
    return round(price * 100, 2)


def compute_expected_value(
    probability_estimate: float,
    market_price: float,
) -> dict:
    """
    Compute expected value of a bet.

    Args:
        probability_estimate: Your estimated probability (0-1)
        market_price: Current market price (0-1)

    Returns:
        Dict with EV analysis
    """
    if market_price <= 0 or market_price >= 1:
        return {"error": "Market price must be between 0 and 1"}

    # If you buy YES at market_price:
    #   Win:  (1 - market_price) with probability = probability_estimate
    #   Lose: market_price with probability = (1 - probability_estimate)
    ev_yes = (probability_estimate * (1 - market_price)) - ((1 - probability_estimate) * market_price)

    # If you buy NO at (1 - market_price):
    no_price = 1 - market_price
    ev_no = ((1 - probability_estimate) * (1 - no_price)) - (probability_estimate * no_price)

    return {
        "your_estimate": f"{probability_estimate * 100:.1f}%",
        "market_price": f"{market_price * 100:.1f}%",
        "edge": f"{(probability_estimate - market_price) * 100:.1f}%",
        "ev_buy_yes": round(ev_yes, 4),
        "ev_buy_no": round(ev_no, 4),
        "recommendation": "BUY YES" if ev_yes > 0.01 else ("BUY NO" if ev_no > 0.01 else "NO EDGE"),
        "kelly_fraction_yes": round(ev_yes / (1 - market_price), 4) if ev_yes > 0 and market_price < 1 else 0,
    }
