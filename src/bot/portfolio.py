"""
Portfolio and position management for paper trading.

Domain-agnostic — works with any market that has token_id / slug.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a single trading position."""
    token_id: str
    match_slug: str
    outcome: str  # e.g., "England", "Bitcoin > 100k"
    side: str  # "YES" or "NO"
    entry_price: float
    shares: float
    cost_basis: float
    entry_time: datetime
    reasoning: str = ""
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    status: str = "OPEN"  # "OPEN" or "CLOSED"

    @property
    def pnl(self) -> float:
        """Calculate P&L for this position."""
        if self.status == "CLOSED" and self.exit_price is not None:
            return (self.exit_price * self.shares) - self.cost_basis
        return 0.0

    def current_value(self, current_price: float) -> float:
        """Calculate current market value of position."""
        return current_price * self.shares

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L (for open positions)."""
        if self.status == "OPEN":
            return self.current_value(current_price) - self.cost_basis
        return 0.0


@dataclass
class Portfolio:
    """Manages trading portfolio state."""
    starting_capital: float = 1000.0
    current_cash: float = 1000.0
    open_positions: list[Position] = field(default_factory=list)
    closed_positions: list[Position] = field(default_factory=list)

    def can_open_position(self, cost: float) -> bool:
        """Check if we have enough cash for a trade."""
        return self.current_cash >= cost

    def open_position(self, position: Position) -> bool:
        """Open a new position."""
        if not self.can_open_position(position.cost_basis):
            logger.warning(
                "Insufficient cash: $%.2f < $%.2f",
                self.current_cash, position.cost_basis,
            )
            return False

        self.current_cash -= position.cost_basis
        self.open_positions.append(position)
        logger.info(
            "Opened position: %s @ $%.3f (%d shares, cost: $%.2f)",
            position.outcome, position.entry_price,
            position.shares, position.cost_basis,
        )
        return True

    def close_position(
        self, token_id: str, exit_price: float, exit_time: datetime
    ) -> Optional[Position]:
        """Close an existing position."""
        for i, pos in enumerate(self.open_positions):
            if pos.token_id == token_id:
                pos.exit_price = exit_price
                pos.exit_time = exit_time
                pos.status = "CLOSED"

                proceeds = exit_price * pos.shares
                self.current_cash += proceeds

                self.open_positions.pop(i)
                self.closed_positions.append(pos)

                logger.info(
                    "Closed position: %s @ $%.3f (P&L: $%.2f)",
                    pos.outcome, exit_price, pos.pnl,
                )
                return pos

        logger.warning("Position not found for token_id: %s", token_id)
        return None

    def get_position_for_match(self, match_slug: str) -> Optional[Position]:
        """Find open position for a specific market."""
        for pos in self.open_positions:
            if pos.match_slug == match_slug:
                return pos
        return None

    def get_total_value(self, current_prices: dict[str, float] | None = None) -> float:
        """Calculate total portfolio value (cash + open positions)."""
        total = self.current_cash
        if current_prices:
            for pos in self.open_positions:
                if pos.token_id in current_prices:
                    total += pos.current_value(current_prices[pos.token_id])
                else:
                    total += pos.cost_basis
        else:
            for pos in self.open_positions:
                total += pos.cost_basis
        return total

    def get_pnl(self, current_prices: dict[str, float] | None = None) -> float:
        """Calculate total P&L percentage."""
        total_value = self.get_total_value(current_prices)
        if self.starting_capital == 0:
            return 0.0
        return ((total_value - self.starting_capital) / self.starting_capital) * 100

    def get_realized_pnl(self) -> float:
        """Get total realized P&L from closed positions."""
        return sum(pos.pnl for pos in self.closed_positions)

    def get_unrealized_pnl(self, current_prices: dict[str, float]) -> float:
        """Get total unrealized P&L from open positions."""
        total = 0.0
        for pos in self.open_positions:
            if pos.token_id in current_prices:
                total += pos.unrealized_pnl(current_prices[pos.token_id])
        return total
