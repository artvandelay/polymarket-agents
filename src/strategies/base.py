"""
Base strategy interface for trading strategies.

Domain-agnostic — strategies receive a MarketSnapshot and return a TradeDecision.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from ..polymarket.models import MarketSnapshot


# ── Trade decision ───────────────────────────────────────────────────

@dataclass
class TradeDecision:
    """Represents a trading decision from a strategy."""
    action: str  # "BUY", "SELL", "HOLD", "PASS"
    token_id: Optional[str] = None
    outcome: Optional[str] = None  # e.g., "England", "Bitcoin > 100k"
    side: str = "YES"  # "YES" or "NO"
    position_size: float = 0.0  # Dollar amount
    confidence: float = 0.0  # 0-1
    edge: Optional[float] = None  # Estimated edge percentage
    reasoning: str = ""  # Human-readable explanation
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Prompt builder protocol ──────────────────────────────────────────

class PromptBuilder(Protocol):
    """
    Protocol that domain-specific modules implement to provide
    LLM prompts tailored to their domain (cricket, crypto, etc.).
    """

    def build_analysis_prompt(
        self,
        snapshot: MarketSnapshot,
        portfolio_summary: dict[str, Any],
        existing_position: Optional[Any] = None,
    ) -> str:
        """Build a prompt for the LLM to analyze a market and decide."""
        ...


# ── Base strategy ────────────────────────────────────────────────────

class BaseStrategy(ABC):
    """Base class that all trading strategies must implement."""

    def __init__(self, config: dict):
        """
        Initialize strategy with config.

        Args:
            config: Strategy-specific configuration dict
        """
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name for logging."""
        ...

    @abstractmethod
    async def analyze(
        self,
        snapshot: MarketSnapshot,
        portfolio_summary: dict[str, Any],
        existing_position: Optional[Any] = None,
    ) -> TradeDecision:
        """
        Analyze market data and return trading decision.

        Args:
            snapshot: Current market data snapshot
            portfolio_summary: Dict with cash, total_value, open_positions count
            existing_position: Existing position for this market (if any)

        Returns:
            TradeDecision with action and reasoning
        """
        ...
