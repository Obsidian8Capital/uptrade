# PRP-005: Data Updater Service

**Wave:** 1 (Data Pipeline)
**Dependencies:** PRP-003 (PolygonClient), PRP-004 (TimescaleDB read/write)
**Branch:** `feature/prp-005-data-updater`
**Estimated Effort:** 2.5 hours
**PRD Reference:** PRD-001, Epic 1 (US-1.3)

---

## Context Layer

### Goal
Create a scheduled data update service that continuously polls Polygon.io for new candles across configured symbols and timeframes, writing results to TimescaleDB. Provide both a VBT-native `DataUpdater` approach and a simple asyncio loop as a standalone service entry point.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- VectorBT Pro `vbt.DataUpdater` (for VBT-native update scheduling)
- Python asyncio (for standalone service loop)
- `src/data/polygon_client.py` (PRP-003) for Polygon pulls
- `src/data/tsdb.py` (PRP-004) for TimescaleDB writes
- `src/config/settings.py` (PRP-001) for configuration
- `src/config/bot_config.py` (PRP-002) for symbol/timeframe extraction from bot configs

### Files to Create
1. `src/data/updater.py` — Data updater service class
2. `scripts/run_updater.py` — Entry point script for standalone execution

### Architecture Decisions
- **Dual approach**: Support VBT's `DataUpdater.update_every()` pattern for tight VBT integration, but also provide a simple asyncio polling loop for Docker deployment as a long-running service
- **Configurable per-symbol intervals** — different timeframes need different poll intervals (1m data needs polling every 60s, 1h data every 3600s)
- **Default update schedule**: poll at 80% of the timeframe duration (e.g., 1m timeframe polls every 48 seconds to catch candle close promptly)
- **Graceful shutdown** — handle SIGINT/SIGTERM for clean Docker stops
- **Error recovery** — if a poll fails, log the error and continue; do not crash the service
- **Startup backfill** — on service start, do an incremental update to fill any gaps from downtime
- **Health file** — write a heartbeat timestamp to `/tmp/updater_health` for Docker healthcheck

### VBT DataUpdater Reference
```python
import vectorbtpro as vbt

# VBT's built-in update pattern:
data = vbt.PolygonData.pull("X:BTCUSD", timeframe="1 minute")
updater = data.create_updater()
updater.update_every(seconds=60)  # Blocks, polls every 60s
# Access latest: updater.data.get()
```

### PRP-003 PolygonClient API (created by PRP-003)
```python
from src.data.polygon_client import PolygonClient

client = PolygonClient()
df = client.pull_ohlcv("X:BTCUSD", "1m", start="2024-01-01", end="2024-12-31")
client.incremental_update("X:BTCUSD", "1m", read_fn=get_latest_timestamp, write_fn=write_ohlcv)
```

### PRP-004 TSDB API (created by PRP-004)
```python
from src.data.tsdb import write_ohlcv, read_ohlcv, get_latest_timestamp

write_ohlcv(df, symbol="X:BTCUSD", timeframe="1m")
latest = get_latest_timestamp("X:BTCUSD", "1m")
```

---

## Task Layer

### Tasks

1. Create `src/data/updater.py` with class `DataUpdaterService`:

   1a. **Constructor** `__init__(self, symbols: list[str] = None, timeframes: list[str] = None, settings=None)`:
   - Accept list of symbols (Polygon format, e.g., `["X:BTCUSD", "X:ETHUSD"]`)
   - Accept list of timeframes (e.g., `["1m", "5m", "1h"]`)
   - If neither provided, load from settings or use defaults: `["X:BTCUSD"]` and `["1m"]`
   - Create `PolygonClient` instance from PRP-003
   - Store references to `write_ohlcv` and `get_latest_timestamp` from PRP-004
   - Initialize logger via `get_logger("data_updater")`
   - Store `_running: bool = False` flag for graceful shutdown
   - Store `_health_file: str = "/tmp/updater_health"`

   1b. **Method** `get_poll_interval(self, timeframe: str) -> float`:
   - Return polling interval in seconds based on timeframe
   - Map: `{"1m": 48, "5m": 240, "15m": 720, "30m": 1440, "1h": 2880, "4h": 11520, "1d": 69120}`
   - Formula: 80% of timeframe duration in seconds
   - Configurable override via constructor kwarg `poll_intervals: dict = None`

   1c. **Method** `startup_backfill(self)`:
   - For each symbol/timeframe combo, run `self.client.incremental_update()` with tsdb read/write functions
   - Log summary: symbols updated, rows added, time ranges
   - This fills any gaps from service downtime

   1d. **Method** `_update_once(self, symbol: str, timeframe: str)`:
   - Single poll cycle for one symbol/timeframe
   - Call `self.client.incremental_update(symbol, timeframe, read_fn=get_latest_timestamp, write_fn=write_ohlcv)`
   - Log: symbol, timeframe, new rows (or "no new data")
   - Write heartbeat to `self._health_file` with current timestamp
   - Handle exceptions: log error, do not raise (service must continue)

   1e. **Async method** `_poll_loop(self, symbol: str, timeframe: str)`:
   - Async loop that runs while `self._running` is True
   - Call `_update_once(symbol, timeframe)` (wrap in `asyncio.to_thread()` since Polygon/TSDB calls are sync)
   - Sleep for `get_poll_interval(timeframe)` seconds
   - On exception: log, sleep 30 seconds, retry

   1f. **Async method** `run(self)`:
   - Set `self._running = True`
   - Run `startup_backfill()` first (via `asyncio.to_thread()`)
   - Create async tasks for each symbol/timeframe combo via `_poll_loop()`
   - Use `asyncio.gather()` to run all poll loops concurrently
   - Register SIGINT/SIGTERM handlers to set `self._running = False`
   - Log: "DataUpdater started with N symbol/timeframe pairs"
   - On shutdown: log "DataUpdater shutting down gracefully"

   1g. **Method** `stop(self)`:
   - Set `self._running = False`
   - Log: "Stop requested"

   1h. **Class method** `from_bot_configs(cls, config_dir: str = "src/config/examples/") -> DataUpdaterService`:
   - Load all bot configs from directory via PRP-002's `load_all_configs()`
   - Extract unique (symbol, timeframe) pairs from all configs
   - Map `pair` + `data.symbol_override` to Polygon symbol format
   - Return `DataUpdaterService(symbols=..., timeframes=...)`
   - This allows the updater to automatically track what data the bots need

2. Create `scripts/run_updater.py` — standalone entry point:

   2a. Parse command-line arguments:
   - `--symbols` — comma-separated Polygon symbols (default: from bot configs)
   - `--timeframes` — comma-separated timeframes (default: "1m,5m,1h")
   - `--config-dir` — path to bot config directory (default: "src/config/examples/")
   - `--log-level` — logging level (default: "INFO")

   2b. Setup:
   - Call `setup_logging(level=args.log_level)`
   - If `--symbols` provided, create `DataUpdaterService(symbols=..., timeframes=...)`
   - Else, create via `DataUpdaterService.from_bot_configs(args.config_dir)`

   2c. Run:
   - Call `asyncio.run(updater.run())`
   - Print startup banner with configured symbols and timeframes

   2d. Make script executable:
   - Add `#!/usr/bin/env python3` shebang
   - Add `if __name__ == "__main__":` guard

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify imports
python3 -c "
from src.data.updater import DataUpdaterService
print('DataUpdaterService imported OK')
"

# Verify class methods exist
python3 -c "
import inspect
from src.data.updater import DataUpdaterService
methods = ['get_poll_interval', 'startup_backfill', 'run', 'stop', 'from_bot_configs']
for m in methods:
    assert hasattr(DataUpdaterService, m), f'Missing method: {m}'
    sig = inspect.signature(getattr(DataUpdaterService, m))
    print(f'{m}{sig}')
print('All methods present')
"

# Verify poll interval mapping
python3 -c "
from src.data.updater import DataUpdaterService
svc = DataUpdaterService.__new__(DataUpdaterService)
svc._poll_intervals = None
# Test the default intervals
assert svc.get_poll_interval('1m') < 60, '1m poll should be < 60s'
assert svc.get_poll_interval('1h') < 3600, '1h poll should be < 3600s'
print('Poll intervals OK')
"

# Verify script exists and is parseable
python3 -c "
import ast
with open('scripts/run_updater.py') as f:
    tree = ast.parse(f.read())
print('run_updater.py syntax OK')
# Check for argparse usage
src = open('scripts/run_updater.py').read()
assert 'argparse' in src or 'ArgumentParser' in src, 'Script must use argparse'
assert '__main__' in src, 'Script must have __main__ guard'
print('Script structure OK')
"

# Verify async run method
python3 -c "
import inspect
from src.data.updater import DataUpdaterService
assert inspect.iscoroutinefunction(DataUpdaterService.run), 'run() must be async'
print('Async run OK')
"
```

### Success Criteria
- [ ] `src/data/updater.py` exists with `DataUpdaterService` class
- [ ] `scripts/run_updater.py` exists as executable entry point with argparse
- [ ] `DataUpdaterService` has methods: `get_poll_interval`, `startup_backfill`, `run`, `stop`, `from_bot_configs`
- [ ] `run()` is an async method using `asyncio.gather()` for concurrent polling
- [ ] `get_poll_interval()` returns 80% of timeframe duration by default
- [ ] `startup_backfill()` runs incremental update for all symbol/timeframe pairs on startup
- [ ] Graceful shutdown via SIGINT/SIGTERM handling (sets `_running = False`)
- [ ] Error recovery — individual poll failures are logged but do not crash the service
- [ ] Health file written at `/tmp/updater_health` with heartbeat timestamps
- [ ] `from_bot_configs()` extracts symbols/timeframes from bot deployment YAML configs
- [ ] `run_updater.py` supports `--symbols`, `--timeframes`, `--config-dir`, `--log-level` arguments
- [ ] All imports from PRP-003 (`PolygonClient`) and PRP-004 (`write_ohlcv`, `get_latest_timestamp`) are used
