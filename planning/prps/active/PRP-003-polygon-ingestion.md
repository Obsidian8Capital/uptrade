# PRP-003: Polygon Data Ingestion

**Wave:** 1 (Data Pipeline)
**Dependencies:** PRP-001 (Docker stack with TimescaleDB running)
**Branch:** `feature/prp-003-polygon-ingestion`
**Estimated Effort:** 3 hours
**PRD Reference:** PRD-001, Epic 1 (US-1.2)

---

## Context Layer

### Goal
Create a Polygon.io data ingestion client that wraps VectorBT Pro's `vbt.PolygonData` to pull crypto OHLCV data and write it to TimescaleDB. Support both batch historical backfill (arbitrary date ranges) and incremental updates (latest candles only).

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- VectorBT Pro (`vbt.PolygonData.pull()`)
- Polygon.io REST API (via VBT's built-in wrapper)
- SQLAlchemy + psycopg2 for TimescaleDB writes
- pandas DataFrames as intermediate format
- Python asyncio (for future integration with updater service)

### Files to Create
1. `src/data/__init__.py` — Data package init with exports
2. `src/data/polygon_client.py` — Polygon ingestion client class

### Files Modified (created by PRP-001/PRP-004)
- Reads from `src/config/settings.py` for `POLYGON_API_KEY` and DB connection string

### Architecture Decisions
- **Wrap `vbt.PolygonData`** rather than calling Polygon REST API directly — VBT handles pagination, rate limits, and DataFrame formatting
- **Polygon symbol format** for crypto is `X:BTCUSD` (prefix `X:` for crypto pairs)
- **VBT returns DataFrame** with columns: Open, High, Low, Close, Volume, VWAP, Transactions — map these to our TimescaleDB `ohlcv` schema
- **Batch backfill** accepts `start` and `end` date strings, pulls all data in that range
- **Incremental update** computes the last timestamp in TimescaleDB for a given symbol/timeframe and pulls only newer data
- **Configurable symbol list and timeframes** via a dict config or the `BotDeploymentConfig` from PRP-002
- **Rate limit awareness** — Polygon free tier allows 5 requests/min; add configurable delay between requests
- **Error handling** — retry on transient failures (HTTP 429, 5xx), log and skip on permanent failures (invalid symbol)
- **Uses PRP-004's `write_ohlcv()`** for database writes — this PRP focuses on the Polygon pull logic and orchestration

### Key VBT API Reference
```python
import vectorbtpro as vbt

# Pull crypto OHLCV from Polygon
data = vbt.PolygonData.pull(
    "X:BTCUSD",
    timeframe="1 minute",
    start="2024-01-01",
    end="2024-12-31",
)
df = data.get()  # Returns pandas DataFrame with Open, High, Low, Close, Volume columns
# Also available: data.get("VWAP"), data.get("Transactions")
```

### TimescaleDB ohlcv Schema (from PRP-001 init.sql)
```sql
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
```

---

## Task Layer

### Tasks

1. Create `src/data/__init__.py`:
   - Import and export `PolygonClient` from `polygon_client`
   - Add package docstring

2. Create `src/data/polygon_client.py` with class `PolygonClient`:

   2a. **Constructor** `__init__(self, settings=None)`:
   - Accept optional `Settings` object (from `src/config/settings.py`), or load default
   - Store `polygon_api_key` and `db_url` from settings
   - Configure VBT Polygon API key: `vbt.PolygonData.set_custom_settings(client_config=dict(api_key=key))`
   - Store configurable `request_delay` (default 0.5 seconds between Polygon calls for rate limiting)
   - Initialize logger via `src/logging_config.get_logger("polygon_client")`

   2b. **Method** `pull_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame`:
   - Call `vbt.PolygonData.pull(symbol, timeframe=timeframe, start=start, end=end)`
   - Extract DataFrame via `data.get()`
   - Rename columns to match TimescaleDB schema: `Open->open, High->high, Low->low, Close->close, Volume->volume`
   - Add `vwap` column from `data.get("VWAP")` if available (else NaN)
   - Add `trade_count` column from `data.get("Transactions")` if available (else None)
   - Add `symbol` and `timeframe` columns
   - Set index name to `time` (VBT returns DatetimeIndex)
   - Return the formatted DataFrame
   - Log: symbol, timeframe, date range, row count
   - Handle exceptions: log error, return empty DataFrame on failure

   2c. **Method** `backfill(self, symbol: str, timeframe: str, start: str, end: str, write_fn=None)`:
   - Pull data via `pull_ohlcv()`
   - If `write_fn` is provided (callable), call `write_fn(df, symbol, timeframe)` — this will be PRP-004's `write_ohlcv()`
   - If no `write_fn`, just return the DataFrame
   - Log summary: rows pulled, date range covered

   2d. **Method** `backfill_batch(self, symbols: list[str], timeframes: list[str], start: str, end: str, write_fn=None)`:
   - Iterate over all symbol/timeframe combinations
   - Call `backfill()` for each
   - Sleep `self.request_delay` seconds between calls (rate limiting)
   - Return dict of `{(symbol, timeframe): row_count}` summarizing results
   - Log total symbols processed, total rows

   2e. **Method** `incremental_update(self, symbol: str, timeframe: str, read_fn=None, write_fn=None)`:
   - If `read_fn` is provided, call `read_fn(symbol, timeframe)` to get the latest timestamp from DB
   - If no latest timestamp found, default to 7 days ago
   - Set `start` to latest timestamp + 1 second, `end` to "now"
   - Call `pull_ohlcv()` and `write_fn()` if provided
   - Return the DataFrame
   - Log: symbol, timeframe, rows added, time range

   2f. **Method** `incremental_update_batch(self, symbols: list[str], timeframes: list[str], read_fn=None, write_fn=None)`:
   - Same pattern as `backfill_batch()` but calls `incremental_update()` per combo
   - Return summary dict

3. Add module-level convenience functions:
   - `create_polygon_client(settings=None) -> PolygonClient` — factory function
   - `POLYGON_TIMEFRAME_MAP` — dict mapping our timeframe strings to VBT format:
     ```python
     POLYGON_TIMEFRAME_MAP = {
         "1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes",
         "30m": "30 minutes", "1h": "1 hour", "4h": "4 hours",
         "1d": "1 day", "1w": "1 week",
     }
     ```

4. Add `CRYPTO_SYMBOL_MAP` — helper dict mapping common pair names to Polygon format:
   ```python
   CRYPTO_SYMBOL_MAP = {
       "BTCUSD": "X:BTCUSD", "ETHUSD": "X:ETHUSD", "SOLUSD": "X:SOLUSD",
       "BTC-USDT": "X:BTCUSD", "ETH-USDC": "X:ETHUSD", "SOL-USDT": "X:SOLUSD",
   }
   ```

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade
python3 -c "
from src.data.polygon_client import PolygonClient, POLYGON_TIMEFRAME_MAP, CRYPTO_SYMBOL_MAP
print('PolygonClient imported OK')
print('Timeframes:', list(POLYGON_TIMEFRAME_MAP.keys()))
print('Symbols:', list(CRYPTO_SYMBOL_MAP.keys()))
"
python3 -c "
from src.data import PolygonClient
client = PolygonClient.__new__(PolygonClient)  # test class exists without connecting
print('Class instantiation OK')
print('Methods:', [m for m in dir(client) if not m.startswith('_')])
"
# Verify all expected methods exist
python3 -c "
from src.data.polygon_client import PolygonClient
import inspect
methods = ['pull_ohlcv', 'backfill', 'backfill_batch', 'incremental_update', 'incremental_update_batch']
for m in methods:
    assert hasattr(PolygonClient, m), f'Missing method: {m}'
    sig = inspect.signature(getattr(PolygonClient, m))
    print(f'{m}{sig}')
print('All methods present')
"
```

### Success Criteria
- [ ] `src/data/__init__.py` exists and exports `PolygonClient`
- [ ] `src/data/polygon_client.py` exists with `PolygonClient` class
- [ ] `PolygonClient` has all 5 methods: `pull_ohlcv`, `backfill`, `backfill_batch`, `incremental_update`, `incremental_update_batch`
- [ ] `pull_ohlcv` returns a DataFrame with columns matching TimescaleDB schema (time, symbol, timeframe, open, high, low, close, volume, vwap, trade_count)
- [ ] `POLYGON_TIMEFRAME_MAP` maps 8 timeframe strings to VBT format
- [ ] `CRYPTO_SYMBOL_MAP` maps common pair names to Polygon `X:` format
- [ ] `backfill_batch` accepts symbol/timeframe lists and iterates with rate limiting
- [ ] `incremental_update` computes start from last DB timestamp
- [ ] All imports resolve without errors (assuming VBT Pro and dependencies installed)
- [ ] Logger is initialized and used for key operations
