"""Polymarket data models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OutcomeSnapshot(BaseModel):
    token_id: str
    buy_price: float = 0.0
    sell_price: float = 0.0
    spread: float = 0.0


class MarketSnapshot(BaseModel):
    slug: str
    title: str = ""
    volume: float = 0.0
    liquidity: float = 0.0
    outcomes: dict[str, OutcomeSnapshot] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
