"""Cricket prompt builder."""

from __future__ import annotations

from typing import Any, Optional

from ...polymarket.models import MarketSnapshot


class CricketPromptBuilder:

    def build_analysis_prompt(
        self,
        snapshot: MarketSnapshot,
        portfolio_summary: dict[str, Any],
        existing_position: Optional[Any] = None,
    ) -> str:
        outcomes_str = "\n".join(
            f"  {name}: {data.buy_price * 100:.1f}c"
            for name, data in snapshot.outcomes.items()
        )

        position_str = ""
        if existing_position:
            pos = existing_position
            curr_price = snapshot.outcomes.get(pos.outcome)
            curr_val = (
                pos.current_value(curr_price.buy_price) if curr_price else pos.cost_basis
            )
            position_str = f"\nPOSITION: {pos.outcome} @ {pos.entry_price * 100:.1f}c, {pos.shares:.0f} shares (basis ${pos.cost_basis:.2f}, now ${curr_val:.2f})\n"

        cash = portfolio_summary.get("current_cash", 0)
        open_cnt = portfolio_summary.get("open_positions", 0)

        prompt = f"""{snapshot.title}
Vol: ${snapshot.volume:,.0f} | Liq: ${snapshot.liquidity:,.0f}
{outcomes_str}

Cash: ${cash:,.2f} | Open: {open_cnt}{position_str}
Decide: BUY/SELL/HOLD/PASS. Size: 5-10% of cash.

Format:
ACTION: [BUY/SELL/HOLD/PASS]
OUTCOME: [name or N/A]
SIDE: [YES/NO]
SIZE: [dollar amount]
CONFIDENCE: [0-1]
EDGE: [% or N/A]
REASONING: [brief explanation]"""

        return prompt
