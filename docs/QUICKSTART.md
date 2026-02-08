# Trading Bot - Quick Start Guide

## What We Built

A fully functional AI-powered paper trading bot that:
- Monitors cricket matches on Polymarket every 5 minutes
- Uses Claude (via OpenRouter) to analyze markets and make decisions
- Manages portfolio with $1,000 starting capital
- Tracks positions, P&L, and trades in SQLite database
- Pluggable strategy system (easy to add new strategies)
- Clean separation: MCP server / Trading bot / Strategies

## Project Structure

```
src/
├── polymarket/            # Pure API clients
│   ├── gamma.py          # Gamma API client
│   ├── clob.py           # CLOB API client
│   ├── models.py         # Pydantic models
│   └── utils.py          # Utilities
│
├── mcp/                  # MCP servers
│   ├── base.py          # Base server with generic tools
│   └── cricket.py       # Cricket-specific server
│
├── bot/                 # Trading bot framework
│   ├── base.py          # Main bot runner
│   ├── portfolio.py     # Portfolio management
│   ├── database.py      # SQLite persistence
│   └── config.py        # Config loader
│
├── domains/             # Domain implementations
│   └── cricket/
│       ├── bot.py       # Cricket bot runner
│       ├── scanner.py   # Market scanner
│       └── prompts.py   # LLM prompts
│
└── strategies/          # Pluggable strategies
    ├── base.py          # Strategy interface
    └── llm.py           # Claude-powered AI

config.yaml              # Bot configuration
.env                     # API keys (OpenRouter)
data/trading.db          # Trading database
```

## Running the Bot

### Option 1: Quick Test (3 minutes)
```bash
cd ~/LLM-apps/polymarket-live
source ~/pyenv/polymarket-cricket/bin/activate

# Run for ~3 minutes with 1-minute intervals
python -m src.domains.cricket.bot --duration 0.05 --interval 1
```

### Option 2: Full Session (2 hours)
```bash
# Default: 2 hours, 5-minute intervals
python -m src.domains.cricket.bot
```

### Option 3: Custom Duration
```bash
# 30 minutes, check every 3 minutes
python -m src.domains.cricket.bot --duration 0.5 --interval 3
```

### Option 4: In tmux (recommended)
```bash
tmux new-session -s trading-bot
python -m src.domains.cricket.bot --duration 2 --interval 5

# Detach: Ctrl+B, then D
# Reattach: tmux attach -t trading-bot
```

## Configuration

Edit `config.yaml` to customize:

```yaml
trading:
  starting_capital: 1000      # Starting cash
  interval_minutes: 5         # How often to scan
  duration_hours: 2           # How long to run
  max_position_size_pct: 30   # Max 30% per trade
  
strategies:
  ai:
    model: anthropic/claude-3.5-sonnet
    temperature: 0.7
    min_confidence: 0.6       # Only trade when 60%+ confident
```

## What the Bot Does

Every cycle:
1. **Scans** for active cricket matches with moneyline markets
2. **Collects** odds, volume, liquidity for each match
3. **Analyzes** using Claude AI:
   - Identifies value opportunities
   - Calculates position size
   - Considers portfolio risk
4. **Executes** paper trades (BUY/SELL/HOLD/PASS)
5. **Tracks** P&L and updates database

## AI Decision Making

Claude analyzes each match and considers:
- **Value**: Is the market price different from true probability?
- **Momentum**: Did odds shift significantly?
- **Liquidity**: Can we enter/exit easily?
- **Risk**: Portfolio concentration and diversification
- **Position sizing**: How much to risk based on edge

Example decision:
```
ACTION: PASS
REASONING: England heavily favored at 95.6¢ with only 4.4% upside.
Spread is tight but no value edge detected. Market is efficient.
Would need England to drop below 92¢ or Nepal to rise above 8¢ for value.
```

## Next Steps

### 1. Integrate Real MCP Data
Currently using mock data. To use real Polymarket data:
- Update market scanner to call real MCP tools
- Connect to MCP client (polymarket-cricket server)
- Use `get_match()`, `get_odds()`, `get_orderbook()`

### 2. Add More Strategies
Create new strategy files in `src/strategies/`:
- `momentum.py` - Trade on price movements
- `value.py` - Pure EV-based betting
- `arbitrage.py` - Exploit pricing inefficiencies

### 3. Enhance Logging
- Add structured logging to files
- Create trade history reports
- Export P&L charts

### 4. Real Trading (Future)
- Integrate Polymarket wallet
- Add order placement via CLOB API
- Implement safety limits and killswitch

## Testing

The bot is currently set up with:
- Mock market data (England vs Nepal, Afghanistan vs NZ)
- Working AI strategy (Claude makes real decisions)
- Full portfolio management
- Database persistence

Everything works end-to-end. Next step is real MCP data integration.

## Dependencies

Already installed:
- `mcp` - MCP server framework
- `httpx` - HTTP client for OpenRouter
- `aiosqlite` - Async SQLite
- `python-dotenv` - Environment variables
- `pyyaml` - Config loader

## Key Features

**Methodical design**: Built component by component, tested each piece  
**Clean architecture**: MCP / Trading / Strategies separated  
**Pluggable strategies**: Easy to swap or add new strategies  
**Real AI analysis**: Claude makes contextual trading decisions  
**Paper trading**: No real money, just simulations  
**Full portfolio tracking**: Positions, P&L, trade history

---

**v0.1.0** - Ready for research and development
