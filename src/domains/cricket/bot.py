"""
Cricket trading bot — wires the generic BaseBot with cricket-specific
market scanning, data collection, and LLM prompts.

Entry point for the script workflow:
    python -m src.domains.cricket.bot [--duration 2] [--interval 5] [--config config.yaml]
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from ...bot.base import BaseBot
from ...bot.config import load_config
from ...strategies.llm import LLMStrategy
from ...polymarket.models import MarketSnapshot
from .scanner import scan_active_matches, collect_market_data
from .prompts import CricketPromptBuilder


class CricketBot(BaseBot):
    """Cricket-specific trading bot."""

    async def scan_markets(self, min_volume: float = 5000) -> list[str]:
        """Discover active cricket matches above volume threshold."""
        return await scan_active_matches(min_volume=min_volume)

    async def collect_market_data(self, slug: str) -> MarketSnapshot:
        """Collect live market data for a cricket match."""
        return await collect_market_data(slug)


def _build_bot(config: dict) -> CricketBot:
    """Construct a CricketBot from config."""
    strategy_cfg = config.get("strategies", {}).get("ai", {})
    prompt_builder = CricketPromptBuilder()
    strategy = LLMStrategy(strategy_cfg, prompt_builder)
    return CricketBot(strategy=strategy, config=config)


async def run(
    duration_hours: float = 2,
    interval_minutes: float = 5,
    config_path: str = "config.yaml",
) -> None:
    """High-level entry: load config, build bot, run loop."""
    config = load_config(config_path)
    bot = _build_bot(config)

    print("Initializing Cricket Trading Bot...\n")
    await bot.run(
        duration_hours=duration_hours,
        interval_minutes=interval_minutes,
    )


def main() -> None:
    """CLI entry point."""
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
