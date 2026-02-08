"""SQLite database for persistence."""

import aiosqlite
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/trading.db"

CREATE_TABLES_SQL = """
-- Portfolio state snapshots
CREATE TABLE IF NOT EXISTS portfolio_state (
    timestamp INTEGER PRIMARY KEY,
    cash REAL NOT NULL,
    total_value REAL NOT NULL,
    pnl REAL NOT NULL,
    num_open_positions INTEGER DEFAULT 0
);

-- Individual positions (open and closed)
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id TEXT NOT NULL,
    match_slug TEXT NOT NULL,
    outcome TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    shares REAL NOT NULL,
    cost_basis REAL NOT NULL,
    entry_time INTEGER NOT NULL,
    exit_price REAL,
    exit_time INTEGER,
    pnl REAL,
    reasoning TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN'
);

-- Trading decisions log
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    cycle INTEGER,
    match_slug TEXT NOT NULL,
    action TEXT NOT NULL,
    reasoning TEXT,
    confidence REAL,
    edge REAL,
    market_data TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_match ON positions(match_slug);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp);
"""


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    async def init_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(CREATE_TABLES_SQL)
            await db.commit()

    async def reset(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DROP TABLE IF EXISTS portfolio_state")
            await db.execute("DROP TABLE IF EXISTS positions")
            await db.execute("DROP TABLE IF EXISTS decisions")
            await db.commit()
        await self.init_schema()
