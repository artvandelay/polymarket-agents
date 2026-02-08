"""
Base trading bot runner — domain-agnostic.

Defines the generic trading loop:
  scan -> collect -> analyze -> decide -> execute -> sleep

Subclass and implement ``scan_markets`` and ``collect_market_data``
for your domain (cricket, crypto, …).
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

from .database import Database
from .portfolio import Portfolio, Position
from ..strategies.base import BaseStrategy, TradeDecision
from ..polymarket.models import MarketSnapshot

logger = logging.getLogger(__name__)


class BaseBot(ABC):
    """
    Domain-agnostic trading bot.

    Subclass must implement:
        - ``scan_markets``   — discover active markets (returns list of slugs)
        - ``collect_market_data`` — fetch full snapshot for a slug
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        config: dict,
    ):
        self.strategy = strategy
        self.config = config
        self._last_prices: dict[str, float] = {}

        # Will be initialised in ``run``
        self.db: Optional[Database] = None
        self.portfolio: Optional[Portfolio] = None

    # ── Abstract hooks ───────────────────────────────────────────────

    @abstractmethod
    async def scan_markets(self, min_volume: float = 5000) -> list[str]:
        """Return slugs of active markets to evaluate this cycle."""
        ...

    @abstractmethod
    async def collect_market_data(self, slug: str) -> MarketSnapshot:
        """Collect a full MarketSnapshot for the given slug."""
        ...

    # ── Main loop ────────────────────────────────────────────────────

    async def run(
        self,
        duration_hours: float = 2,
        interval_minutes: float = 5,
    ) -> None:
        """Run the trading loop for ``duration_hours``."""

        cfg = self.config
        trading_cfg = cfg.get("trading", {})

        # --- Init DB ---
        self.db = Database(cfg.get("database", {}).get("path", "data/trading.db"))
        await self.db.init_schema()
        print(f"  Database ready: {self.db.db_path}\n")

        # --- Init portfolio ---
        starting = trading_cfg.get("starting_capital", 1000)
        self.portfolio = Portfolio(starting_capital=starting, current_cash=starting)
        print(f"  Starting capital: ${self.portfolio.starting_capital:,.2f}\n")

        print(f"  Strategy: {self.strategy.name}")
        print(f"  Duration: {duration_hours} hours")
        print(f"  Interval: {interval_minutes} minutes\n")
        print("=" * 60)

        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        cycle = 0

        while datetime.now() < end_time:
            cycle += 1
            cycle_start = datetime.now()

            # Collect current prices for portfolio valuation
            current_prices = self._collect_position_prices()

            print(f"\n{'=' * 60}")
            print(f"Trading Cycle #{cycle} @ {cycle_start:%H:%M:%S}")
            print(f"{'=' * 60}")
            print(
                f"Portfolio: ${self.portfolio.get_total_value(current_prices):,.2f} | "
                f"Cash: ${self.portfolio.current_cash:,.2f} | "
                f"Open: {len(self.portfolio.open_positions)} positions | "
                f"P&L: {self.portfolio.get_pnl(current_prices):+.2f}%"
            )
            print()

            # 1. Scan
            min_vol = cfg.get("markets", {}).get("min_volume", 5000)
            slugs = await self.scan_markets(min_volume=min_vol)
            print(f"[SCAN] Found {len(slugs)} active markets")

            # 2. Analyse each market
            for slug in slugs:
                await self._process_market(slug, cycle)

            # 3. Cycle summary (re-collect prices after processing)
            current_prices = self._collect_position_prices()
            print(f"\n{'=' * 60}")
            print(f"End of Cycle #{cycle}")
            print(f"Portfolio Value: ${self.portfolio.get_total_value(current_prices):,.2f}")
            print(f"Cash: ${self.portfolio.current_cash:,.2f}")
            print(f"Open Positions: {len(self.portfolio.open_positions)}")
            print(f"Total P&L: {self.portfolio.get_pnl(current_prices):+.2f}%")

            # 4. Sleep
            elapsed = (datetime.now() - cycle_start).total_seconds()
            sleep_secs = max(0, interval_minutes * 60 - elapsed)
            if sleep_secs > 0:
                next_at = datetime.now() + timedelta(seconds=sleep_secs)
                print(f"\nNext scan at {next_at:%H:%M:%S}")
                await asyncio.sleep(sleep_secs)
            else:
                print("\nCycle took longer than interval!")

        # --- Final report ---
        self._final_report(duration_hours, cycle)

    # ── Per-market processing ────────────────────────────────────────

    async def _process_market(self, slug: str, cycle: int) -> None:
        try:
            snapshot = await self.collect_market_data(slug)
            print(f"\n[ANALYZE] {snapshot.title}")
            print(f"    Volume: ${snapshot.volume:,.0f} | Liquidity: ${snapshot.liquidity:,.0f}")

            existing = self.portfolio.get_position_for_match(slug)
            if existing:
                outcome_data = snapshot.outcomes.get(existing.outcome)
                if outcome_data:
                    current_price = outcome_data.buy_price
                    # Cache price for portfolio valuation
                    self._last_prices[existing.token_id] = current_price
                    unrealized = existing.unrealized_pnl(current_price)
                    print(
                        f"    EXISTING: {existing.outcome} @ {existing.entry_price * 100:.1f}c "
                        f"(Unrealized P&L: ${unrealized:+.2f})"
                    )
                else:
                    logger.warning(
                        "Outcome %s not found in snapshot for %s",
                        existing.outcome, slug,
                    )

            portfolio_summary = {
                "current_cash": self.portfolio.current_cash,
                "total_value": self.portfolio.get_total_value(self._collect_position_prices()),
                "open_positions": len(self.portfolio.open_positions),
            }

            decision = await self.strategy.analyze(snapshot, portfolio_summary, existing)

            print(f"    [DECISION] {decision.action}")
            if decision.confidence > 0:
                print(f"       Outcome: {decision.outcome}")
                print(f"       Size: ${decision.position_size:.2f}")
                print(f"       Confidence: {decision.confidence * 100:.0f}%")
                if decision.edge is not None:
                    print(f"       Edge: {decision.edge:.1f}%")
            print(f"       Reasoning: {decision.reasoning}")

            if decision.action == "BUY" and decision.token_id and decision.outcome:
                self._execute_buy(decision, snapshot)
            elif decision.action == "SELL" and existing:
                self._execute_sell(decision, snapshot, existing)

        except Exception as e:
            logger.error("Error processing %s: %s", slug, e)
            print(f"    Error: {e}")

    # ── Execution ────────────────────────────────────────────────────

    def _execute_buy(self, decision: TradeDecision, snapshot: MarketSnapshot) -> None:
        outcome_data = snapshot.outcomes.get(decision.outcome)
        if not outcome_data:
            logger.warning("Outcome %s not in snapshot, skipping BUY", decision.outcome)
            return

        buy_price = outcome_data.buy_price
        shares = decision.position_size / buy_price if buy_price else 0

        position = Position(
            token_id=decision.token_id,
            match_slug=snapshot.slug,
            outcome=decision.outcome,
            side=decision.side,
            entry_price=buy_price,
            shares=shares,
            cost_basis=decision.position_size,
            entry_time=datetime.now(),
            reasoning=decision.reasoning,
        )

        if self.portfolio.open_position(position):
            self._last_prices[decision.token_id] = buy_price
            print(
                f"    BUY executed: {decision.outcome} @ {buy_price * 100:.1f}c "
                f"({shares:.0f} shares, ${decision.position_size:.2f})"
            )

    def _execute_sell(
        self,
        decision: TradeDecision,
        snapshot: MarketSnapshot,
        existing: Position,
    ) -> None:
        outcome_data = snapshot.outcomes.get(existing.outcome)
        if not outcome_data:
            logger.warning("Outcome %s not in snapshot, skipping SELL", existing.outcome)
            return

        sell_price = outcome_data.sell_price
        closed = self.portfolio.close_position(existing.token_id, sell_price, datetime.now())
        if closed:
            self._last_prices.pop(existing.token_id, None)
            print(
                f"    SELL executed: {closed.outcome} @ {sell_price * 100:.1f}c "
                f"(P&L: ${closed.pnl:+.2f})"
            )

    # ── Price cache for portfolio valuation ───────────────────────────

    def _collect_position_prices(self) -> dict[str, float]:
        """Return cached token prices for open positions."""
        return dict(self._last_prices)

    # ── Report ───────────────────────────────────────────────────────

    def _final_report(self, duration_hours: float, cycles: int) -> None:
        p = self.portfolio
        prices = self._collect_position_prices()
        print(f"\n\n{'=' * 60}")
        print("TRADING SESSION COMPLETE")
        print(f"{'=' * 60}")
        print(f"Duration: {duration_hours} hours ({cycles} cycles)")
        print(f"Starting Capital: ${p.starting_capital:,.2f}")
        print(f"Final Value: ${p.get_total_value(prices):,.2f}")
        total_pnl = p.get_total_value(prices) - p.starting_capital
        print(f"Total P&L: ${total_pnl:+,.2f} ({p.get_pnl(prices):+.2f}%)")
        print(f"Realized P&L: ${p.get_realized_pnl():+,.2f}")
        print(f"Closed Trades: {len(p.closed_positions)}")
        print(f"Open Positions: {len(p.open_positions)}")
        print(f"{'=' * 60}")
