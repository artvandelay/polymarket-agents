# Polymarket Live

An AI-powered trading bot and MCP server for analyzing cricket betting markets on Polymarket.

## Overview

This project provides two complementary tools:

1. **MCP Server** - Read-only research tools for Cursor/AI agents to analyze Polymarket markets
2. **Trading Bot** - Autonomous paper trading bot using Claude Sonnet for decision-making

Both share the same underlying API clients and work with real-time Polymarket data.

## Features

- AI-powered strategy using Claude Sonnet via OpenRouter
- Real-time market data from Polymarket's Gamma and CLOB APIs
- Portfolio management with P&L tracking
- Pluggable strategy system for easy extensibility
- SQLite persistence for trades and portfolio state
- Configurable via YAML
- Paper trading only (no real money)

## Architecture

The project follows a layered architecture with clear separation of concerns:

```
src/
├── polymarket/              # Pure API clients (domain-agnostic)
│   ├── gamma.py            # Gamma API (events/markets discovery)
│   ├── clob.py             # CLOB API (pricing/orderbook)
│   ├── models.py           # Pydantic models
│   └── utils.py            # Shared utilities
│
├── mcp/                    # MCP servers for Cursor integration
│   ├── base.py            # Base server with generic tools
│   └── cricket.py         # Cricket-specific server
│
├── bot/                   # Trading bot framework (domain-agnostic)
│   ├── base.py           # Base bot with main loop
│   ├── config.py         # Configuration loader
│   ├── database.py       # SQLite persistence
│   └── portfolio.py      # Portfolio/position management
│
├── domains/              # Domain-specific implementations
│   └── cricket/
│       ├── bot.py       # Cricket bot runner
│       ├── scanner.py   # Market scanner
│       └── prompts.py   # LLM prompts
│
└── strategies/           # Pluggable trading strategies
    ├── base.py          # Base strategy interface
    └── llm.py           # LLM-powered strategy
```

### Design Principles

- **Domain-agnostic core** - API clients and bot framework work with any market type
- **Pluggable strategies** - Easy to add momentum, value, or arbitrage strategies
- **Shared HTTP clients** - Efficient connection reuse across API calls
- **Concurrent API calls** - Uses `asyncio.gather()` for parallel data fetching
- **Type safety** - Pydantic models for data validation
- **Clean separation** - MCP server and trading bot are independent

## Quick Start

### Prerequisites

- Python 3.11+
- OpenRouter API key (for Claude access)
- Virtual environment in `~/pyenv/polymarket-cricket`

### Installation

```bash
# Clone the repository
git clone https://github.com/artvandelay/polymarket-agents.git
cd polymarket-agents

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install mcp httpx pydantic websockets python-dotenv pyyaml aiosqlite
```

### Configuration

1. Copy `.env.example` to `.env` and add your OpenRouter API key:

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
```

2. Review `config.yaml` to adjust trading parameters:

```yaml
trading:
  starting_capital: 1000
  interval_minutes: 5
  duration_hours: 2
  max_position_size_pct: 30

strategies:
  ai:
    model: anthropic/claude-3.5-sonnet
    temperature: 0.7
    min_confidence: 0.6
```

### Running the Bot

**Quick test (3 minutes):**
```bash
python -m src.domains.cricket.bot --duration 0.05 --interval 1
```

**Standard session (2 hours):**
```bash
python -m src.domains.cricket.bot
```

**In tmux (recommended):**
```bash
tmux new-session -s trading-bot
python -m src.domains.cricket.bot
# Detach: Ctrl+B, then D
# Reattach: tmux attach -t trading-bot
```

### Running the MCP Server

The MCP server provides 10 tools for market research:

```bash
# Start the server (typically called by Cursor)
polymarket-cricket
```

See `AGENTS.md` for full documentation of available tools and workflows.

## How It Works

### Trading Loop

1. **Scan** - Find active cricket matches on Polymarket
2. **Collect** - Fetch market data (odds, volume, liquidity)
3. **Analyze** - Claude evaluates each market for value
4. **Decide** - Generate BUY/SELL/HOLD/PASS decision
5. **Execute** - Place paper trade if decision is BUY/SELL
6. **Sleep** - Wait for next interval

### AI Decision Making

For each market, Claude analyzes:

- Current odds vs estimated true probability
- Market efficiency (volume, liquidity, spread)
- Portfolio risk and position sizing
- Expected value and edge calculation

Decisions include confidence level, reasoning, and position size recommendation.

### Example Output

```
============================================================
Trading Cycle #1 @ 15:56:56
============================================================
Portfolio: $1,000.00 | Cash: $1,000.00 | Open: 0 positions | P&L: +0.00%

[SCAN] Found 2 active matches

[ANALYZE] T20 World Cup: England vs Nepal (Game 1)
    Volume: $202,000 | Liquidity: $79,000
    [DECISION] PASS
       Reasoning: England at 95.6¢ appears efficient. Potential 
       return (4.4%) doesn't justify the risk. Preserving capital 
       for markets with clearer edges.

[ANALYZE] T20 World Cup: Afghanistan vs New Zealand (Game 1)
    Volume: $437,000 | Liquidity: $73,000
    [DECISION] PASS
       Confidence: 90%
       Reasoning: 99.9¢ offers no realistic edge. Afghanistan at 
       0.1¢ is too risky. Best to avoid this market.

============================================================
End of Cycle #1
Portfolio Value: $1,000.00
Cash: $1,000.00
Open Positions: 0
Total P&L: +0.00%

Next scan at 15:57:56
```

## Database Schema

The bot stores all state in SQLite (`data/trading.db`):

### portfolio_state
```sql
timestamp INTEGER PRIMARY KEY
cash REAL
total_value REAL
pnl REAL
num_open_positions INTEGER
```

### positions
```sql
id INTEGER PRIMARY KEY
token_id TEXT           -- Polymarket token ID
match_slug TEXT         -- Match identifier
outcome TEXT            -- Team/outcome name
side TEXT               -- YES or NO
entry_price REAL        -- Entry price (0-1)
shares REAL             -- Number of shares
cost_basis REAL         -- Total cost
entry_time INTEGER      -- Unix timestamp
exit_price REAL         -- Exit price (if closed)
exit_time INTEGER       -- Exit timestamp
pnl REAL                -- Profit/loss
reasoning TEXT          -- AI reasoning
status TEXT             -- OPEN or CLOSED
```

### decisions
```sql
id INTEGER PRIMARY KEY
timestamp INTEGER
cycle INTEGER           -- Cycle number
match_slug TEXT
action TEXT             -- BUY/SELL/HOLD/PASS
reasoning TEXT          -- AI reasoning
confidence REAL         -- 0-1
edge REAL               -- Estimated edge %
market_data TEXT        -- JSON snapshot
```

## Adding New Strategies

The bot uses a pluggable strategy system. Create a new strategy by:

1. Subclass `BaseStrategy` in `src/strategies/`
2. Implement `name` property and `analyze()` method
3. Register in `src/domains/cricket/bot.py`
4. Configure in `config.yaml`

Example:

```python
from src.strategies.base import BaseStrategy, TradeDecision

class MomentumStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "Momentum Strategy"
    
    async def analyze(self, snapshot, portfolio, existing_position):
        momentum = self._calculate_momentum(snapshot)
        
        if momentum > self.config["threshold"]:
            return TradeDecision(
                action="BUY",
                outcome="Team with momentum",
                position_size=100,
                confidence=0.7,
                reasoning=f"Strong momentum: +{momentum}% in last hour"
            )
        
        return TradeDecision(action="PASS", reasoning="No momentum")
```

## MCP Server Tools

The cricket MCP server provides 10 tools:

**Discovery:**
- `list_cricket_leagues` - Get all available cricket series
- `list_cricket_matches` - List active/upcoming matches
- `get_match` - Get full details for a specific match
- `search_events` - Text search across events
- `get_market_types` - List valid market types

**Pricing:**
- `get_odds` - Current buy/sell/midpoint prices
- `get_orderbook` - Full bid/ask depth
- `get_spread` - Bid-ask spread
- `get_price_history` - Historical price movement

**Analysis:**
- `analyze_odds` - Expected value calculator with Kelly criterion

See `AGENTS.md` for detailed documentation and example workflows.

## Project Status

**Version:** 0.1.0

This is an early release focused on paper trading and research. The core functionality is implemented:

- API clients operational
- Bot executes trading loops
- AI decision-making integrated
- Portfolio tracking implemented
- Database persistence functional

**Not yet implemented:**
- Real MCP data integration (currently uses mock data in some places)
- WebSocket streaming for live updates
- Stop-loss/take-profit automation
- Real money trading (intentionally excluded)

## Roadmap

**v0.2 - Real Data:**
- Full MCP integration
- WebSocket price streams
- Historical backtesting

**v0.3 - Advanced Strategies:**
- Momentum strategy
- Value/EV strategy
- Multi-agent consensus

**v0.4 - Risk Management:**
- Automated stop-loss/take-profit
- Position sizing limits
- Drawdown protection

**v1.0 - Production:**
- Web dashboard
- Advanced analytics
- Production monitoring

Real money trading support is not planned. This tool is designed for research and learning.

## Important Notes

### Paper Trading Only

This bot does not execute real trades. It simulates trades to track performance without risking money. Use cases:

- Learning betting strategy
- Testing AI decision-making
- Understanding market dynamics
- Strategy development

### API Costs

OpenRouter charges per token for Claude API calls:
- Approximately $0.002 per decision (500 tokens)
- 2 hours at 5-min intervals: ~24 cycles × 2 matches × $0.002 = ~$0.10/session

### Data Sources

- **Gamma API** - Event/market discovery (public, no auth required)
- **CLOB API** - Pricing and orderbook data (public, no auth required)

## Troubleshooting

**"OPENROUTER_API_KEY not found"**
- Ensure `.env` file exists in project root
- Verify key format: `OPENROUTER_API_KEY=sk-or-v1-...`
- Check the key has not expired

**"HTTP 401 Unauthorized"**
- Invalid API key - verify in OpenRouter dashboard
- Insufficient credits - add funds to OpenRouter account

**"Database locked"**
- Another bot instance is running
- Kill process: `pkill -f "python.*cricket.bot"`
- Or use different database path in config

**Bot produces no output**
- Python output may be buffered
- Run with: `python -u -m src.domains.cricket.bot`
- Or redirect to file: `python -m src.domains.cricket.bot > bot.log 2>&1`

## License

MIT License - Free to use, modify, and distribute.

## Credits

- MCP Framework by Anthropic
- Polymarket public APIs (Gamma and CLOB)
- Claude 3.5 Sonnet via OpenRouter
- Built with Python, httpx, aiosqlite, pydantic, pyyaml

---

**v0.1.0** - Built for research, designed for extensibility.

For detailed MCP tool documentation, see `AGENTS.md`.  
For quick start examples, see `docs/QUICKSTART.md`.
