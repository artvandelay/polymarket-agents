# Polymarket Cricket Research MCP - Agent Guide

## Overview

This workspace contains a **read-only MCP server** for researching cricket betting markets on Polymarket. It provides 10 tools to discover matches, analyze odds, inspect orderbook depth, track historical prices, and calculate expected value. **No trading, no wallet, no authentication required** - pure research and analysis.

## Quick Start

The MCP server `polymarket-cricket` is configured in Cursor and exposes 10 tools. All tools work with **live data** from Polymarket's Gamma API (sports/events) and CLOB API (prices/orderbook).

## Available Tools

### 1. Discovery Tools

- **`list_cricket_leagues`** - Get all cricket leagues/series  
  Returns 6 leagues: IPL, T20 World Cup, International (crint), India (crind), WPL, WT20 WC Qualifiers  
  Each has a `series_id` needed for filtering matches.

- **`list_cricket_matches`** - List active/upcoming matches  
  **Required params**: `series_id` (from `list_cricket_leagues`), optional `limit`, `include_closed`  
  Returns match title, slug, volume, liquidity, and odds for all sub-markets.

- **`get_match`** - Get full details for a specific match  
  **Required params**: `slug` (e.g., `crint-afg-nzl-2026-02-08`)  
  Returns all sub-markets with **token IDs** needed for CLOB pricing tools.

- **`search_events`** - Text search across all events  
  **Required params**: `query` (e.g., "afghanistan")  
  Note: Searches ALL Polymarket events, not just cricket.

- **`get_market_types`** - List valid cricket bet types  
  Returns 6 cricket-specific types: `moneyline`, `cricket_toss_winner`, `cricket_completed_match`, `cricket_toss_match_double`, `cricket_most_sixes`, `cricket_team_top_batter`

### 2. Pricing & Orderbook Tools

All pricing tools require a **`token_id`** (get from `get_match` or `list_cricket_matches` results).

- **`get_odds`** - Current buy/sell price + midpoint  
  Returns prices as decimals (0.96 = 96¢) and implied probabilities.

- **`get_orderbook`** - Full bid/ask depth  
  Shows where liquidity sits - useful for understanding support/resistance and slippage.

- **`get_spread`** - Bid-ask spread  
  Tight spread (1-2¢) = high liquidity. Wide spread = thin market.

- **`get_price_history`** - Historical price movement  
  **Params**: `token_id`, `interval` (1m/5m/1h/1d), `fidelity` (resolution in minutes)  
  Returns timestamped price points showing how odds shifted over time.

### 3. Analysis Tool

- **`analyze_odds`** - Expected value calculator  
  **Required params**: `your_probability` (0-1), `market_price` (0-1)  
  Returns edge, EV, recommendation (BUY YES/NO), and Kelly fraction for bet sizing.

## Typical Workflows

### Workflow 1: Find and Analyze a Match

```
1. list_cricket_leagues
   → Get series_id for "crint" (International cricket)

2. list_cricket_matches(series_id="10528")
   → Browse active T20 World Cup matches
   → Note the "slug" for the match you want

3. get_match(slug="crint-afg-nzl-2026-02-08")
   → Get full event with all sub-markets and token_ids
   → Extract token_id for the outcome you want to bet on

4. get_odds(token_id="110851405964408375011304493493992064924931184506995375679172504761641721591327")
   → Current odds: 96% implied probability for New Zealand

5. get_price_history(token_id="...", interval="1h")
   → See how odds moved: 69.5¢ → 92¢ (huge swing!)

6. analyze_odds(your_probability=0.85, market_price=0.965)
   → EV: -11.5% edge = overpriced, skip or bet NO
```

### Workflow 2: Monitor Orderbook Depth

```
1. get_match(slug="crint-gbr-npl-2026-02-08")
   → England vs Nepal match

2. get_orderbook(token_id="...")
   → 46 bid levels, 3 ask levels
   → $4,164 at 96¢ bid, $130 at 97¢ ask

3. get_spread(token_id="...")
   → 1¢ spread = very liquid, low slippage
```

### Workflow 3: Calculate Betting Edge

```
1. get_odds(token_id="...")
   → Market: 96.5% implied probability

2. analyze_odds(your_probability=0.90, market_price=0.965)
   → Your estimate: 90%
   → Market: 96.5%
   → Edge: -6.5% (market overpriced)
   → Recommendation: BUY NO (fade the favorite)
   → Kelly fraction: 0 (no bet)
```

## Key Concepts

### Token IDs
- Every market outcome has a unique `token_id` (long numeric string)
- You get token IDs from `get_match` or `list_cricket_matches`
- All CLOB pricing tools (`get_odds`, `get_orderbook`, `get_spread`, `get_price_history`) require a token ID

### Prices & Odds
- Prices are in **decimal format**: `0.96` = 96¢ = 96% implied probability
- **Buy price** = what you pay to bet YES on that outcome
- **Sell price** = what you receive if you sell your position
- **Midpoint** = average of buy/sell, best estimate of "fair" price

### Market Types
- **moneyline**: Who wins the match (most common, highest volume)
- **cricket_toss_winner**: Who wins the coin toss (50/50, low edge)
- **cricket_completed_match**: Will match finish without rain/cancellation?
- **cricket_toss_match_double**: Combined toss + match outcome
- **cricket_most_sixes**: Which team hits more sixes
- **cricket_team_top_batter**: Which team's batter scores most runs

### Volume & Liquidity
- **Volume**: Total amount traded (higher = more popular market)
- **Liquidity**: Current depth in orderbook (higher = easier to trade)
- **Spread**: Difference between buy/sell (tighter = more liquid)

### Expected Value (EV)
- **Edge**: Your probability - Market probability (positive = opportunity)
- **EV**: Expected profit per $1 bet (positive = profitable long-term)
- **Kelly fraction**: Optimal bet size as % of bankroll (0 = no bet)

## Live Data Examples

From real market as of Feb 8, 2026:

**Afghanistan vs New Zealand (T20 World Cup)**
- Volume: $395k (highly popular)
- New Zealand odds: 7.5¢ buy (92.5% implied to win)
- Afghanistan odds: 92.5¢ buy (7.5% underdog)
- Toss winner: Afghanistan 99.95% (already determined)
- Completed match: 99.9% YES (weather looks good)
- Price movement: NZL jumped 69.5¢ → 92¢ in 1 hour (major line move!)

**England vs Nepal**
- Volume: $199k
- England: 95.7% favorite (dominant team)
- Nepal: 4.3% underdog
- Spread: 1¢ (very liquid)
- Orderbook: $4,164 at 96¢ bid (strong support)

## Project Structure

```
/Users/jigar/LLM-apps/polymarket-live/
  src/
    gamma.py        -- Gamma API client (sports discovery, events)
    clob.py         -- CLOB API client (prices, orderbook, analysis)
    server.py       -- MCP server (10 tools, stdio transport)
  pyproject.toml    -- Dependencies: mcp, httpx, pydantic, websockets
  .env              -- Config (LOG_LEVEL=INFO)
  AGENTS.md         -- This file
```

**Virtual environment**: `~/pyenv/polymarket-cricket`  
**MCP config**: `~/.cursor/mcp.json` → `polymarket-cricket` server

## APIs Used

- **Gamma API** (`https://gamma-api.polymarket.com`) - Sports/events discovery
- **CLOB API** (`https://clob.polymarket.com`) - Pricing, orderbook, history

Both APIs are **public, no authentication required**.

## Tips for Agents

1. **Always start with discovery**: `list_cricket_leagues` → `list_cricket_matches` → `get_match`
2. **Get token IDs first**: Extract from `get_match` before calling pricing tools
3. **Check price history**: A big recent move suggests new information (injury, weather, lineup change)
4. **Compare EV**: If your estimate differs significantly from market, there may be value
5. **Watch the spread**: Tight spread (<2¢) = liquid, wide spread (>5¢) = be careful
6. **Volume matters**: High-volume markets are more efficient (harder to find edge)
7. **Search is fuzzy**: `search_events` returns ALL Polymarket events, not just cricket - filter manually

## Limitations

- **Read-only**: No trading, no order placement (by design - user trades manually)
- **No live scores**: WebSocket streaming not implemented (could be added if needed)
- **No historical depth**: Price history shows midpoint only, not full orderbook snapshots
- **Search is global**: `search_events` searches all Polymarket, not cricket-specific

## Next Steps

For new agents in a chat session:
1. Ask user which cricket match they want to analyze
2. Use `list_cricket_leagues` + `list_cricket_matches` to browse options
3. Pull full match data with `get_match`
4. Analyze odds, orderbook, and price history
5. Calculate EV if user has an opinion on the outcome
6. Explain findings and suggest value opportunities

**Goal**: Help the user learn betting strategy, understand market dynamics, and identify value - not to place orders.
