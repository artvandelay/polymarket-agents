"""CLOB API client for pricing and orderbook."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .utils import API_TIMEOUT

logger = logging.getLogger(__name__)

CLOB_BASE = "https://clob.polymarket.com"

_client = httpx.AsyncClient(timeout=API_TIMEOUT)

async def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{CLOB_BASE}{path}"
    resp = await _client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


async def get_price(token_id: str, side: str = "buy") -> dict:
    return await _get("/price", params={"token_id": token_id, "side": side})


async def get_midpoint(token_id: str) -> dict:
    return await _get("/midpoint", params={"token_id": token_id})


async def get_prices(token_ids: list[str], side: str = "buy") -> list[dict]:
    import asyncio
    
    async def fetch_price(tid: str) -> dict:
        try:
            p = await get_price(tid, side)
            return {"token_id": tid, **p}
        except httpx.HTTPStatusError as e:
            logger.warning("Price fetch failed for %s (%s): %s", tid, side, e)
            return {"token_id": tid, "error": str(e)}
    
    return await asyncio.gather(*[fetch_price(tid) for tid in token_ids])


async def get_orderbook(token_id: str) -> dict:
    return await _get("/book", params={"token_id": token_id})


async def get_spread(token_id: str) -> dict:
    try:
        return await _get("/spread", params={"token_id": token_id})
    except httpx.HTTPStatusError as exc:
        logger.warning("Spread fetch failed for %s: %s", token_id, exc)
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


async def get_price_history(
    token_id: str,
    interval: str = "1h",
    fidelity: int = 60,
) -> list[dict]:
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


def compute_implied_probability(price: float) -> float:
    return round(price * 100, 2)


def compute_expected_value(
    probability_estimate: float,
    market_price: float,
) -> dict:
    if market_price <= 0 or market_price >= 1:
        return {"error": "Market price must be between 0 and 1"}

    # EV = prob_win * payout - prob_lose * cost
    ev_yes = (probability_estimate * (1 - market_price)) - ((1 - probability_estimate) * market_price)
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
