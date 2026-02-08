"""Cricket market scanner."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ...polymarket import gamma, clob
from ...polymarket.models import MarketSnapshot, OutcomeSnapshot
from ...polymarket.utils import safe_json
from .constants import CRICKET_KEYWORDS

logger = logging.getLogger(__name__)


async def scan_active_matches(min_volume: float = 5000) -> list[str]:
    all_sports = await gamma.list_sports()
    cricket_series_ids = [
        s.get("series")
        for s in all_sports
        if any(kw in s.get("sport", "").lower() for kw in CRICKET_KEYWORDS)
        and s.get("series")
    ]

    if not cricket_series_ids:
        logger.warning("No cricket leagues found on Polymarket")
        return []

    slugs: list[str] = []
    for series_id in cricket_series_ids:
        try:
            events = await gamma.list_events(
                series_id=series_id,
                tag_id="100639",
                active=True,
                closed=False,
                limit=30,
            )
            for e in events:
                vol = e.get("volume", 0)
                vol_num = float(vol) if isinstance(vol, (int, float, str)) else 0
                if vol_num >= min_volume and e.get("slug"):
                    slugs.append(e["slug"])
        except httpx.HTTPStatusError:
            logger.debug("No matches for series %s", series_id)

    logger.info("Scan found %d cricket matches above $%,.0f volume", len(slugs), min_volume)
    return slugs


async def collect_market_data(slug: str) -> MarketSnapshot:
    event = await gamma.get_event_by_slug(slug)
    if not event:
        raise ValueError(f"No event found for slug: {slug}")

    title = event.get("title", slug)
    volume = float(event.get("volume", 0)) if event.get("volume") else 0
    liquidity = float(event.get("liquidity", 0)) if event.get("liquidity") else 0

    outcomes: dict[str, OutcomeSnapshot] = {}
    for market in event.get("markets", []):
        mtype = market.get("sportsMarketType", "")
        if mtype != "moneyline":
            continue

        raw_outcomes = safe_json(market.get("outcomes", "[]"))
        raw_prices = safe_json(market.get("outcomePrices", "[]"))
        raw_tokens = safe_json(market.get("clobTokenIds", "[]"))

        for i, name in enumerate(raw_outcomes):
            token_id = raw_tokens[i] if i < len(raw_tokens) else None
            if not token_id:
                continue

            try:
                buy_resp = await clob.get_price(token_id, "buy")
                sell_resp = await clob.get_price(token_id, "sell")
                buy_price = float(buy_resp.get("price", 0))
                sell_price = float(sell_resp.get("price", 0))
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                logger.warning(
                    "CLOB price fetch failed for %s (%s): %s",
                    token_id,
                    slug,
                    exc,
                )
                buy_price = float(raw_prices[i]) if i < len(raw_prices) else 0
                sell_price = buy_price

            outcomes[name] = OutcomeSnapshot(
                token_id=token_id,
                buy_price=buy_price,
                sell_price=sell_price,
                spread=round(abs(buy_price - sell_price), 4),
            )
        break

    return MarketSnapshot(
        slug=slug,
        title=title,
        volume=volume,
        liquidity=liquidity,
        outcomes=outcomes,
    )


