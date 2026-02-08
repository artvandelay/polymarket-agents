"""Cricket trading bot entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging

from ...bot.base import BaseBot
from ...bot.config import load_config
from ...strategies.llm import ReasoningStrategy
from ...polymarket.models import MarketSnapshot
from .scanner import scan_active_matches, collect_market_data
from .prompts import CricketPromptBuilder


class CricketBot(BaseBot):
    async def scan_markets(self, min_volume: float = 5000) -> list[str]:
        return await scan_active_matches(min_volume=min_volume)

    async def collect_market_data(self, slug: str) -> MarketSnapshot:
        return await collect_market_data(slug)


async def run(
    duration_hours: float = 2,
    interval_minutes: float = 5,
    config_path: str = "config.yaml",
) -> None:
    config = load_config(config_path)
    
    strategy_cfg = config.get("strategies", {}).get("ai", {})
    prompt_builder = CricketPromptBuilder()
    strategy = ReasoningStrategy(strategy_cfg, prompt_builder)
    bot = CricketBot(strategy=strategy, config=config)

    await bot.run(
        duration_hours=duration_hours,
        interval_minutes=interval_minutes,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket Cricket Trading Bot")
    parser.add_argument(
        "--duration", type=float, default=2, help="Duration in hours (default: 2)"
    )
    parser.add_argument(
        "--interval", type=float, default=5, help="Interval in minutes (default: 5)"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Config file path"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(
        run(
            duration_hours=args.duration,
            interval_minutes=args.interval,
            config_path=args.config,
        )
    )


if __name__ == "__main__":
    main()
