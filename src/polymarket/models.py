"""
Pydantic models for Polymarket data.

Shared type definitions used across MCP servers, bots, and strategies.
Only models that are actually consumed by the codebase live here.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OutcomeSnapshot(BaseModel):
    """Live pricing data for a single outcome."""
    token_id: str
    buy_price: float = 0.0
    sell_price: float = 0.0
    spread: float = 0.0


class MarketSnapshot(BaseModel):
    """
    Point-in-time snapshot of a market, used by bot strategies.

    This is the common data format that strategies receive regardless
    of the domain (cricket, crypto, politics, etc.).
    """
    slug: str
    title: str = ""
    volume: float = 0.0
    liquidity: float = 0.0
    outcomes: dict[str, OutcomeSnapshot] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
