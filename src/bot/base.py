"""Base trading bot runner."""

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
    def __init__(
        self,
        strategy: BaseStrategy,
        config: dict,
    ):
        self.strategy = strategy
        self.config = config
        self._last_prices: dict[str, float] = {}

        self.db: Optional[Database] = None
        self.portfolio: Optional[Portfolio] = None

    @abstractmethod
    async def scan_markets(self, min_volume: float = 5000) -> list[str]:
        ...

    @abstractmethod
    async def collect_market_data(self, slug: str) -> MarketSnapshot:
        ...

    async def run(
        self,
        duration_hours: float = 2,
        interval_minutes: float = 5,
    ) -> None:
        cfg = self.config
        trading_cfg = cfg.get("trading", {})

        self.db = Database(cfg.get("database", {}).get("path", "data/trading.db"))
        await self.db.init_schema()

        starting = trading_cfg.get("starting_capital", 1000)
        self.portfolio = Portfolio(starting_capital=starting, current_cash=starting)
        print(f"Capital: ${self.portfolio.starting_capital:,.2f}\n")

        print(f"Strategy: {self.strategy.name}")
        print(f"Duration: {duration_hours}h | Interval: {interval_minutes}m\n")
        print("=" * 60)

        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        cycle = 0

        while datetime.now() < end_time:
            cycle += 1
            cycle_start = datetime.now()

            current_prices = self._collect_position_prices()

            print(f"\n{'=' * 60}")
            print(f"Cycle #{cycle} @ {cycle_start:%H:%M:%S}")
            print(f"{'=' * 60}")
            print(
                f"Value: ${self.portfolio.get_total_value(current_prices):,.2f} | "
                f"Cash: ${self.portfolio.current_cash:,.2f} | "
                f"Positions: {len(self.portfolio.open_positions)} | "
                f"P&L: {self.portfolio.get_pnl(current_prices):+.2f}%"
            )
            print()

            min_vol = cfg.get("markets", {}).get("min_volume", 5000)
            slugs = await self.scan_markets(min_volume=min_vol)

            for slug in slugs:
                await self._process_market(slug, cycle)

            current_prices = self._collect_position_prices()
            print(f"\n{'=' * 60}")
            print(f"Cycle #{cycle} done")
            print(f"Value: ${self.portfolio.get_total_value(current_prices):,.2f} | Cash: ${self.portfolio.current_cash:,.2f} | Positions: {len(self.portfolio.open_positions)} | P&L: {self.portfolio.get_pnl(current_prices):+.2f}%")

            elapsed = (datetime.now() - cycle_start).total_seconds()
            sleep_secs = max(0, interval_minutes * 60 - elapsed)
            if sleep_secs > 0:
                next_at = datetime.now() + timedelta(seconds=sleep_secs)
                print(f"\nNext: {next_at:%H:%M:%S}")
                await asyncio.sleep(sleep_secs)
            else:
                print("\nCycle overran!")

        self._final_report(duration_hours, cycle)

    async def _process_market(self, slug: str, cycle: int) -> None:
        try:
            snapshot = await self.collect_market_data(slug)
            print(f"\n{snapshot.title}")
            print(f"  Vol: ${snapshot.volume:,.0f} | Liq: ${snapshot.liquidity:,.0f}")

            existing = self.portfolio.get_position_for_match(slug)
            if existing:
                outcome_data = snapshot.outcomes.get(existing.outcome)
                if outcome_data:
                    current_price = outcome_data.buy_price
                    self._last_prices[existing.token_id] = current_price
                    unrealized = existing.unrealized_pnl(current_price)
                    print(
                        f"  Pos: {existing.outcome} @ {existing.entry_price * 100:.1f}c "
                        f"(P&L: ${unrealized:+.2f})"
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

            print(f"  [{decision.action}]")
            if decision.confidence > 0:
                print(f"    {decision.outcome} | ${decision.position_size:.2f} | Conf: {decision.confidence * 100:.0f}%", end="")
                if decision.edge is not None:
                    print(f" | Edge: {decision.edge:.1f}%", end="")
                print()
            print(f"    {decision.reasoning}")

            if decision.action == "BUY" and decision.token_id and decision.outcome:
                self._execute_buy(decision, snapshot)
            elif decision.action == "SELL" and existing:
                self._execute_sell(decision, snapshot, existing)

        except Exception as e:
            logger.error("Failed %s: %s", slug, e)
            print(f"  Error: {e}")

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

    def _collect_position_prices(self) -> dict[str, float]:
        return dict(self._last_prices)

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
