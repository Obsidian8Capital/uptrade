# PRP-004: TimescaleDB Read/Write Layer

**Wave:** 1 (Data Pipeline)
**Dependencies:** PRP-001 (Docker stack with TimescaleDB schema initialized)
**Branch:** `feature/prp-004-tsdb-readwrite`
**Estimated Effort:** 3 hours
**PRD Reference:** PRD-001, Epic 1 (US-1.1)

---

## Context Layer

### Goal
Create the TimescaleDB read/write layer that provides Python functions for upserting OHLCV data, reading OHLCV data back as VBT-compatible DataFrames, writing indicator signals, and reading signals. Also create the database engine/session management module.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- SQLAlchemy 2.0+ (Core, not ORM — for performance with time-series bulk ops)
- psycopg2-binary (PostgreSQL driver)
- pandas `read_sql` / `to_sql` for DataFrame I/O
- Connection pooling via SQLAlchemy `create_engine(pool_size=5, max_overflow=10)`

### Files to Create
1. `src/data/db.py` — Database engine and session management
2. `src/data/tsdb.py` — TimescaleDB read/write functions

### Files Modified
- `src/data/__init__.py` — Add exports for `tsdb` and `db` modules (may be created by PRP-003; if not, create it)

### Architecture Decisions
- **SQLAlchemy Core** (not ORM) for bulk time-series operations — ORM overhead is unnecessary for append-only time-series writes
- **Upsert pattern** using PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` for idempotent writes — allows re-ingesting the same data without duplicates
- **Connection pooling** — single engine instance shared across the application via module-level singleton
- **VBT-compatible read format** — `read_ohlcv()` returns a DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume (capitalized, as VBT expects)
- **Chunk writes** — large DataFrames are written in configurable chunk sizes (default 5000 rows) to avoid memory issues
- **Timezone-aware timestamps** — all timestamps stored and read as UTC
- **Parameterized queries** — all SQL uses parameterized queries to prevent injection

### TimescaleDB Schema Reference (from PRP-001 init.sql)
```sql
-- OHLCV hypertable
CREATE TABLE ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    timeframe   TEXT        NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    vwap        DOUBLE PRECISION,
    trade_count INTEGER
);
CREATE UNIQUE INDEX idx_ohlcv_unique ON ohlcv (symbol, timeframe, time);

-- Indicator signals hypertable
CREATE TABLE indicator_signals (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    timeframe   TEXT        NOT NULL,
    indicator   TEXT        NOT NULL,
    signal      INTEGER,           -- -1, 0, 1
    value       DOUBLE PRECISION,  -- indicator raw value
    params      JSONB              -- indicator params snapshot
);
CREATE UNIQUE INDEX idx_signals_unique ON indicator_signals (symbol, timeframe, indicator, time);
```

---

## Task Layer

### Tasks

1. Create `src/data/db.py` — Database engine management:

   1a. **`get_engine(db_url: str = None) -> sqlalchemy.Engine`**:
   - Module-level singleton pattern: store engine in `_engine` global
   - If `db_url` is None, load from `src.config.settings.Settings().database_url`
   - Create engine with: `pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=3600`
   - Return the engine
   - Log: "Database engine created" with connection info (mask password)

   1b. **`get_connection() -> contextmanager`**:
   - Context manager that yields a connection from `get_engine().connect()`
   - Commits on success, rolls back on exception
   - Example usage: `with get_connection() as conn: conn.execute(...)`

   1c. **`reset_engine()`**:
   - Dispose existing engine and reset singleton
   - For testing and reconnection scenarios

   1d. **`check_health() -> bool`**:
   - Execute `SELECT 1` to verify connectivity
   - Return True/False
   - Log result

2. Create `src/data/tsdb.py` — OHLCV read/write functions:

   2a. **`write_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str, chunk_size: int = 5000)`**:
   - Accept a DataFrame with DatetimeIndex and columns: open, high, low, close, volume (and optional vwap, trade_count)
   - Add `symbol` and `timeframe` columns if not present
   - Rename index to `time` column
   - Ensure all timestamps are UTC
   - Use PostgreSQL upsert: `INSERT INTO ohlcv (...) VALUES (...) ON CONFLICT (symbol, timeframe, time) DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high, ...`
   - Write in chunks of `chunk_size` rows
   - Log: symbol, timeframe, rows written
   - Return number of rows written

   2b. **`read_ohlcv(symbol: str, timeframe: str, start: str = None, end: str = None, limit: int = None) -> pd.DataFrame`**:
   - Build SELECT query with optional WHERE clauses for time range
   - Query: `SELECT time, open, high, low, close, volume, vwap, trade_count FROM ohlcv WHERE symbol=:symbol AND timeframe=:timeframe AND time >= :start AND time <= :end ORDER BY time`
   - Use `pd.read_sql()` with the engine
   - Set `time` column as DatetimeIndex
   - Rename columns to VBT format: `open->Open, high->High, low->Low, close->Close, volume->Volume`
   - If `limit` is specified, add `LIMIT :limit` to query
   - Return empty DataFrame with correct columns if no data found
   - Log: symbol, timeframe, rows returned

   2c. **`get_latest_timestamp(symbol: str, timeframe: str) -> datetime | None`**:
   - Query: `SELECT MAX(time) FROM ohlcv WHERE symbol=:symbol AND timeframe=:timeframe`
   - Return the timestamp or None if no data exists
   - Used by PRP-003's incremental update logic

   2d. **`get_ohlcv_stats(symbol: str = None, timeframe: str = None) -> pd.DataFrame`**:
   - Query: `SELECT symbol, timeframe, COUNT(*) as rows, MIN(time) as first, MAX(time) as last FROM ohlcv GROUP BY symbol, timeframe`
   - Optional filter by symbol and/or timeframe
   - Return DataFrame with summary statistics
   - Useful for monitoring data coverage

   2e. **`write_signals(df: pd.DataFrame, symbol: str, timeframe: str, indicator: str, params: dict = None, chunk_size: int = 5000)`**:
   - Accept DataFrame with DatetimeIndex and columns: `signal` (int: -1, 0, 1) and `value` (float)
   - Add `symbol`, `timeframe`, `indicator` columns
   - Add `params` as JSONB (serialize dict to JSON string)
   - Upsert: `INSERT INTO indicator_signals ... ON CONFLICT (symbol, timeframe, indicator, time) DO UPDATE SET signal=EXCLUDED.signal, value=EXCLUDED.value, params=EXCLUDED.params`
   - Write in chunks
   - Log: indicator, symbol, timeframe, rows written
   - Return number of rows written

   2f. **`read_signals(symbol: str, timeframe: str, indicator: str, start: str = None, end: str = None) -> pd.DataFrame`**:
   - Query: `SELECT time, signal, value, params FROM indicator_signals WHERE symbol=:symbol AND timeframe=:timeframe AND indicator=:indicator ...`
   - Set DatetimeIndex on `time`
   - Return DataFrame with signal, value, params columns
   - Return empty DataFrame if no data found

3. Update `src/data/__init__.py`:
   - Add exports: `from src.data.db import get_engine, get_connection, check_health`
   - Add exports: `from src.data.tsdb import write_ohlcv, read_ohlcv, get_latest_timestamp, write_signals, read_signals`

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify imports
python3 -c "
from src.data.db import get_engine, get_connection, reset_engine, check_health
print('db module OK')
from src.data.tsdb import write_ohlcv, read_ohlcv, get_latest_timestamp, get_ohlcv_stats, write_signals, read_signals
print('tsdb module OK')
"

# Verify function signatures
python3 -c "
import inspect
from src.data.tsdb import write_ohlcv, read_ohlcv, get_latest_timestamp, write_signals, read_signals
for fn in [write_ohlcv, read_ohlcv, get_latest_timestamp, write_signals, read_signals]:
    sig = inspect.signature(fn)
    print(f'{fn.__name__}{sig}')
"

# Verify db.py engine creation logic (without actual DB)
python3 -c "
from src.data.db import get_engine
import inspect
src = inspect.getsource(get_engine)
assert 'pool_size' in src, 'Missing pool_size config'
assert 'pool_pre_ping' in src, 'Missing pool_pre_ping config'
print('Engine config OK')
"

# Verify read_ohlcv returns VBT-compatible column names
python3 -c "
import inspect
from src.data.tsdb import read_ohlcv
src = inspect.getsource(read_ohlcv)
assert 'Open' in src or 'rename' in src, 'Must rename columns to VBT format (capitalized)'
print('VBT column format OK')
"

# Verify upsert pattern exists
python3 -c "
import inspect
from src.data.tsdb import write_ohlcv
src = inspect.getsource(write_ohlcv)
assert 'ON CONFLICT' in src or 'on_conflict' in src.lower() or 'upsert' in src.lower(), 'Must use upsert for idempotent writes'
print('Upsert pattern OK')
"
```

### Success Criteria
- [ ] `src/data/db.py` exists with `get_engine`, `get_connection`, `reset_engine`, `check_health`
- [ ] `src/data/tsdb.py` exists with `write_ohlcv`, `read_ohlcv`, `get_latest_timestamp`, `get_ohlcv_stats`, `write_signals`, `read_signals`
- [ ] `get_engine()` uses connection pooling with `pool_size=5, max_overflow=10, pool_pre_ping=True`
- [ ] `get_connection()` is a context manager that commits/rolls back
- [ ] `write_ohlcv()` uses PostgreSQL upsert (`ON CONFLICT ... DO UPDATE`) for idempotent writes
- [ ] `write_ohlcv()` writes in configurable chunk sizes (default 5000)
- [ ] `read_ohlcv()` returns DataFrame with VBT-compatible columns (Open, High, Low, Close, Volume — capitalized)
- [ ] `read_ohlcv()` supports optional `start`, `end`, `limit` parameters
- [ ] `get_latest_timestamp()` returns `datetime | None`
- [ ] `write_signals()` stores indicator name, signal direction, value, and params as JSONB
- [ ] `read_signals()` returns DataFrame with DatetimeIndex
- [ ] All SQL uses parameterized queries (no string interpolation)
- [ ] All timestamps are timezone-aware (UTC)
- [ ] `src/data/__init__.py` exports all public functions
