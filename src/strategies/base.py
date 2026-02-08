"""Base strategy interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from ..polymarket.models import MarketSnapshot


@dataclass
class TradeDecision:
    action: str  # "BUY", "SELL", "HOLD", "PASS"
    token_id: Optional[str] = None
    outcome: Optional[str] = None  # e.g., "England", "Bitcoin > 100k"
    side: str = "YES"  # "YES" or "NO"
    position_size: float = 0.0  # Dollar amount
    confidence: float = 0.0  # 0-1
    edge: Optional[float] = None  # Estimated edge percentage
    reasoning: str = ""  # Human-readable explanation
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptBuilder(Protocol):
    def build_analysis_prompt(
        self,
        snapshot: MarketSnapshot,
        portfolio_summary: dict[str, Any],
        existing_position: Optional[Any] = None,
    ) -> str:
        ...


class BaseStrategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def analyze(
        self,
        snapshot: MarketSnapshot,
        portfolio_summary: dict[str, Any],
        existing_position: Optional[Any] = None,
    ) -> TradeDecision:
        ...
