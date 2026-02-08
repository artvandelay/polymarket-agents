"""
Cricket-specific prompt templates for the LLM strategy.

Implements the PromptBuilder protocol expected by ``strategies.llm.LLMStrategy``.
"""

from __future__ import annotations

from typing import Any, Optional

from ...polymarket.models import MarketSnapshot


class CricketPromptBuilder:
    """Builds LLM prompts tailored to cricket match analysis."""

    def build_analysis_prompt(
        self,
        snapshot: MarketSnapshot,
        portfolio_summary: dict[str, Any],
        existing_position: Optional[Any] = None,
    ) -> str:
        """Build a structured prompt for the LLM to analyse a cricket market."""

        # Format outcomes
        outcomes_str = "\n".join(
            f"  - {name}: {data.buy_price * 100:.1f}c "
            f"(implied prob: {data.buy_price * 100:.1f}%)"
            for name, data in snapshot.outcomes.items()
        )

        # Format existing position if any
        position_str = ""
        if existing_position:
            pos = existing_position
            curr_price = snapshot.outcomes.get(pos.outcome)
            curr_val = (
                pos.current_value(curr_price.buy_price) if curr_price else pos.cost_basis
            )
            position_str = f"""
EXISTING POSITION:
- Outcome: {pos.outcome}
- Entry price: {pos.entry_price * 100:.1f}c
- Shares: {pos.shares:.0f}
- Cost basis: ${pos.cost_basis:.2f}
- Current value: ${curr_val:.2f}
"""

        cash = portfolio_summary.get("current_cash", 0)
        total = portfolio_summary.get("total_value", 0)
        open_cnt = portfolio_summary.get("open_positions", 0)

        prompt = f"""You are a sports betting trader analysing a cricket match on Polymarket.

MARKET DATA:
- Match: {snapshot.title}
- Volume: ${snapshot.volume:,.0f}
- Liquidity: ${snapshot.liquidity:,.0f}
- Outcomes:
{outcomes_str}

PORTFOLIO STATE:
- Cash available: ${cash:,.2f}
- Open positions: {open_cnt}
- Total value: ${total:,.2f}
{position_str}

YOUR TASK:
Analyse this market and decide: BUY, SELL, HOLD, or PASS.

Consider:
1. Is there value? (Is the market price different from your estimate?)
2. Liquidity (Volume: ${snapshot.volume:,.0f})
3. Portfolio risk (Don't over-concentrate)
4. Position sizing (Risk 5-10% of capital on good opportunities)

Return your decision in this EXACT format:
ACTION: [BUY/SELL/HOLD/PASS]
OUTCOME: [team name if BUY/SELL, or N/A]
SIDE: [YES/NO]
SIZE: [dollar amount, e.g., 50]
CONFIDENCE: [0-1, e.g., 0.75]
EDGE: [percentage, e.g., 5.2, or N/A]
REASONING: [2-3 sentences explaining your decision]

Now analyse the market above:"""

        return prompt
