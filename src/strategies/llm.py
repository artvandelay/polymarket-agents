"""
Generic model-powered trading strategy.
"""

import logging
from typing import Any, Optional

import httpx

from .base import BaseStrategy, PromptBuilder, TradeDecision
from ..polymarket.models import MarketSnapshot

logger = logging.getLogger(__name__)


class ReasoningStrategy(BaseStrategy):
    def __init__(self, config: dict, prompt_builder: PromptBuilder):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.model = config.get("model", "anthropic/claude-3.5-sonnet")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 500)
        self.min_confidence = config.get("min_confidence", 0.6)
        self.prompt_builder = prompt_builder

    @property
    def name(self) -> str:
        return f"Reasoning Strategy ({self.model})"

    async def analyze(
        self,
        snapshot: MarketSnapshot,
        portfolio_summary: dict[str, Any],
        existing_position: Optional[Any] = None,
    ) -> TradeDecision:
        prompt = self.prompt_builder.build_analysis_prompt(
            snapshot, portfolio_summary, existing_position
        )

        try:
            response_text = await self._call_llm(prompt)
            decision = self._parse_response(response_text, snapshot)

            if decision.action == "BUY" and decision.confidence < self.min_confidence:
                return TradeDecision(
                    action="PASS",
                    reasoning=(
                        f"Confidence {decision.confidence:.0%} below "
                        f"threshold {self.min_confidence:.0%}"
                    ),
                )

            return decision

        except Exception as e:
            logger.error("LLM strategy error: %s", e)
            return TradeDecision(action="PASS", reasoning=f"Error: {e}")

    async def _call_llm(self, prompt: str) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_response(response: str, snapshot: MarketSnapshot) -> TradeDecision:
        data: dict[str, str] = {}
        for line in response.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                data[key.strip().lower()] = value.strip()

        action = data.get("action", "PASS").upper()
        outcome_raw = data.get("outcome", "N/A")
        outcome: Optional[str] = None if outcome_raw == "N/A" else outcome_raw

        token_id: Optional[str] = None
        if outcome and snapshot.outcomes:
            for name, out_data in snapshot.outcomes.items():
                if name.lower() in outcome.lower():
                    token_id = out_data.token_id
                    outcome = name  # use canonical name
                    break

        def _float(key: str, default: float = 0.0) -> float:
            try:
                return float(data.get(key, str(default)))
            except (ValueError, TypeError):
                return default

        def _opt_float(key: str) -> Optional[float]:
            raw = data.get(key, "N/A")
            if raw == "N/A":
                return None
            try:
                return float(raw)
            except (ValueError, TypeError):
                return None

        return TradeDecision(
            action=action,
            token_id=token_id,
            outcome=outcome,
            side=data.get("side", "YES"),
            position_size=_float("size"),
            confidence=_float("confidence"),
            edge=_opt_float("edge"),
            reasoning=data.get("reasoning", "No reasoning provided"),
            metadata={"raw_response": response},
        )
