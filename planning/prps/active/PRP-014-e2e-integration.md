# PRP-014: End-to-End Integration Test

**Wave:** 5 (Integration)
**Dependencies:** All previous PRPs (PRP-001 through PRP-013)
**Branch:** `feature/prp-014-e2e-integration`
**Estimated Effort:** 4 hours
**PRD Reference:** PRD-001, all Epics (integration validation)

---

## Context Layer

### Goal
Create a comprehensive test suite that validates the entire UpTrade pipeline end-to-end: sample OHLCV data flows through indicators, signals are generated, controllers produce the correct output format, and the data pipeline reads/writes to TimescaleDB correctly. All tests use mocked data and do NOT require live exchange connections, running Docker services, or real API keys.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- pytest — test runner
- pytest-asyncio — async test support
- unittest.mock / pytest-mock — mocking DB connections, API calls
- pandas — sample data generation
- numpy — numerical assertions
- Pydantic — config validation testing

### Files to Create
1. `tests/conftest.py` — Shared pytest fixtures (sample OHLCV data, mock DB engine, mock Hummingbot API)
2. `tests/test_indicators.py` — Indicator smoke tests (all indicators produce valid output on sample data)
3. `tests/test_data_pipeline.py` — Data ingestion and read tests (mocked TimescaleDB)
4. `tests/test_controllers.py` — V2 Controller signal tests (mocked market data provider)
5. `tests/test_e2e.py` — Full pipeline integration test (data -> indicators -> signals -> controller output)

### Architecture Decisions
- **No live services required:** All external dependencies (TimescaleDB, Hummingbot API, Polygon.io, exchanges) are mocked. Tests run in CI without Docker.
- **Sample data:** Generate realistic BTC-USDT 1h OHLCV data (500 bars) with known patterns for deterministic signal testing. Use a fixed random seed for reproducibility.
- **Fixture hierarchy:**
  - `sample_ohlcv_df` — pandas DataFrame with 500 bars of realistic OHLCV data
  - `sample_ohlcv_with_trend` — OHLCV data with an obvious uptrend (for testing long signals)
  - `sample_ohlcv_with_downtrend` — OHLCV data with an obvious downtrend (for short signals)
  - `mock_db_engine` — SQLAlchemy engine that returns sample data without a real DB
  - `mock_hb_api` — httpx mock that simulates Hummingbot API responses
  - `sample_bot_config` — valid `BotDeploymentConfig` for testing
- **Assertion patterns:**
  - Signal values are always in `{-1, 0, 1}`
  - DataFrames have expected columns and no NaN in critical fields
  - Config validation rejects invalid inputs
  - Controller output matches Hummingbot expected format
- **Test isolation:** Each test module is independent. No shared mutable state between tests.
- **Markers:** Use `@pytest.mark.slow` for tests that take >1s (indicator computation on large datasets).

---

## Task Layer

### Tasks

1. Create `tests/conftest.py`:
   - **Fixture: `sample_ohlcv_df`** (scope=session):
     - Generate 500 bars of BTC-USDT 1h OHLCV data
     - Use `np.random.seed(42)` for reproducibility
     - Realistic price range: 38000-45000
     - Columns: `time` (DatetimeIndex), `open`, `high`, `low`, `close`, `volume`
     - `high` always >= `open` and `close`, `low` always <= `open` and `close`
     - Volume between 100-5000
   - **Fixture: `sample_ohlcv_with_trend`** (scope=session):
     - 200 bars with a clear uptrend (each close > previous close on average)
     - Suitable for testing that long signals are generated
   - **Fixture: `sample_ohlcv_with_downtrend`** (scope=session):
     - 200 bars with a clear downtrend
     - Suitable for testing that short signals are generated
   - **Fixture: `mock_db_engine`**:
     - Mock SQLAlchemy engine that intercepts `execute()` calls
     - Returns `sample_ohlcv_df` for OHLCV queries
     - Returns empty DataFrame for other tables
   - **Fixture: `mock_hb_api`**:
     - Uses `unittest.mock.AsyncMock` to mock httpx responses
     - `GET /bot-orchestration/status` returns list of mock bot statuses
     - `POST /bot-orchestration/deploy-v2-script` returns `{"status": "deployed", "bot_name": "test_bot"}`
     - `POST /bot-orchestration/stop-bot` returns `{"status": "stopped"}`
   - **Fixture: `sample_bot_config`**:
     - Returns a valid `BotDeploymentConfig` for SniperProX on BTC-USDT Binance
   - **Fixture: `sample_indicator_signals_df`**:
     - DataFrame with columns: time, symbol, timeframe, indicator, signal, value, params
     - Mix of 1, -1, 0 signals for testing dashboard and combiner

2. Create `tests/test_indicators.py`:
   - `test_sniper_produces_valid_output(sample_ohlcv_df)`:
     - Import SniperProX from `src.indicators.sniper`
     - Run on sample data with default params
     - Assert output has entries and exits arrays
     - Assert all values are boolean or 0/1
     - Assert no NaN in output
   - `test_vzo_produces_valid_output(sample_ohlcv_df)`:
     - Import VZOProX from `src.indicators.vzo`
     - Run on sample data with default params
     - Assert output has vzo values array
     - Assert values are in reasonable range (-100 to 100)
   - `test_spectral_produces_valid_output(sample_ohlcv_df)`:
     - Import SpectralAnalysis from `src.indicators.spectral`
     - Run on sample data
     - Assert output has dominant_period and power
     - Assert dominant_period > 0
   - `test_universal_ma_all_types(sample_ohlcv_df)`:
     - Import UniversalMA from `src.indicators.ma_library`
     - Test at least 5 MA types (SMA, EMA, WMA, Jurik, DEMA)
     - Assert each produces valid output (no NaN after warmup period, correct length)
   - `test_indicator_with_short_data()`:
     - Test indicators with only 10 bars (less than typical lookback)
     - Assert no crash, output has correct length (may have NaN for warmup)
   - `test_signal_combiner(sample_ohlcv_df)`:
     - Import SignalCombiner from `src.signals.combiner`
     - Feed multiple indicator outputs
     - Assert combined signal is in {-1, 0, 1}

3. Create `tests/test_data_pipeline.py`:
   - `test_tsdb_writer_formats_data_correctly()`:
     - Import TSDBWriter from `src.data.tsdb_writer` (or equivalent from PRP-003)
     - Mock the DB connection
     - Call write method with sample OHLCV data
     - Assert SQL insert was called with correct column names and data types
   - `test_tsdb_reader_returns_dataframe(mock_db_engine)`:
     - Import TSDBReader from `src.data.tsdb_reader` (or equivalent from PRP-004)
     - Call read method for symbol="BTC-USDT", timeframe="1h"
     - Assert returned DataFrame has correct columns
     - Assert time column is DatetimeIndex or datetime type
   - `test_data_updater_calls_polygon(sample_ohlcv_df)`:
     - Import DataUpdater from `src.data.updater` (or equivalent from PRP-005)
     - Mock Polygon API client
     - Call update method
     - Assert Polygon API was called with correct symbol
     - Assert data was passed to writer
   - `test_bot_config_loads_yaml(tmp_path)`:
     - Write a sample YAML config to tmp_path
     - Call `load_bot_config()` from PRP-002
     - Assert all fields parsed correctly
     - Assert Pydantic validation passed
   - `test_bot_config_rejects_invalid_yaml(tmp_path)`:
     - Write invalid YAML (missing required fields)
     - Assert `load_bot_config()` raises `ValidationError`
   - `test_indicator_signals_write_read(mock_db_engine)`:
     - Write indicator signals to mock DB
     - Read them back
     - Assert roundtrip preserves data

4. Create `tests/test_controllers.py`:
   - `test_sniper_controller_returns_valid_signal(sample_ohlcv_df)`:
     - Create `SniperController` with `SniperControllerConfig`
     - Mock `market_data_provider.get_candles()` to return sample_ohlcv_df
     - Call `update_processed_data()`
     - Assert `get_signal()` returns int in {-1, 0, 1}
     - Assert `processed_data["signal"]` matches
   - `test_vzo_controller_returns_valid_signal(sample_ohlcv_df)`:
     - Same pattern with VZOController
   - `test_cycle_controller_returns_valid_signal(sample_ohlcv_df)`:
     - Same pattern with CycleController
     - Mock dominant_cycles DB query
   - `test_controller_with_uptrend_generates_long(sample_ohlcv_with_trend)`:
     - Feed uptrend data to SniperController
     - Assert signal is 1 (long) at some point in recent bars
   - `test_controller_with_downtrend_generates_short(sample_ohlcv_with_downtrend)`:
     - Feed downtrend data to SniperController
     - Assert signal is -1 (short) at some point in recent bars
   - `test_controller_config_validation()`:
     - Create config with invalid params (negative leverage, missing pair)
     - Assert Pydantic raises ValidationError
   - `test_controller_registry_complete()`:
     - Import `CONTROLLER_REGISTRY` from `src.controllers`
     - Assert "vbt_sniper", "vbt_vzo", "vbt_cycle" are all registered
     - Assert each maps to the correct class

5. Create `tests/test_e2e.py`:
   - `test_full_pipeline_data_to_signal(sample_ohlcv_df)`:
     1. Start with raw OHLCV DataFrame (simulating data from Polygon/TimescaleDB)
     2. Run SniperProX indicator on the data
     3. Run VZOProX indicator on the data
     4. Feed both outputs to SignalCombiner
     5. Assert combined signal is in {-1, 0, 1}
     6. Assert pipeline completed without errors
   - `test_full_pipeline_config_to_controller_output(sample_ohlcv_df)`:
     1. Load `BotDeploymentConfig` from example YAML
     2. Map indicator name to controller class via `CONTROLLER_REGISTRY`
     3. Create controller with config
     4. Mock market data provider with sample_ohlcv_df
     5. Call `update_processed_data()`
     6. Assert `get_signal()` returns valid integer
     7. Assert the signal format is what Hummingbot PositionExecutor expects
   - `test_deploy_flow_mocked(sample_bot_config, mock_hb_api)`:
     1. Create `BotDeployer` with mocked API
     2. Call `deploy_bot(sample_bot_config)`
     3. Assert API was called with correct payload
     4. Assert response contains bot_name
   - `test_indicator_to_tsdb_roundtrip(sample_ohlcv_df, mock_db_engine)`:
     1. Compute indicator on sample data
     2. Write signal result to mock DB (indicator_signals table format)
     3. Read back from mock DB
     4. Assert data matches
   - `test_cycle_detector_to_dashboard_data(sample_ohlcv_df)`:
     1. Run SpectralAnalysis on sample data
     2. Format output as dominant_cycles table rows
     3. Assert rows have correct schema (time, symbol, timeframe, method, period, power, composite)
     4. Assert period > 0 and power >= 0

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify all test files exist
test -f tests/conftest.py && echo "OK: conftest" || echo "FAIL: conftest"
test -f tests/test_indicators.py && echo "OK: indicators" || echo "FAIL: indicators"
test -f tests/test_data_pipeline.py && echo "OK: data pipeline" || echo "FAIL: data pipeline"
test -f tests/test_controllers.py && echo "OK: controllers" || echo "FAIL: controllers"
test -f tests/test_e2e.py && echo "OK: e2e" || echo "FAIL: e2e"

# Run all tests (will fail if dependencies from previous PRPs aren't implemented yet,
# but the test files themselves should be syntactically valid)
python3 -m py_compile tests/conftest.py && echo "conftest compiles" || echo "conftest FAIL"
python3 -m py_compile tests/test_indicators.py && echo "test_indicators compiles" || echo "test_indicators FAIL"
python3 -m py_compile tests/test_data_pipeline.py && echo "test_data_pipeline compiles" || echo "test_data_pipeline FAIL"
python3 -m py_compile tests/test_controllers.py && echo "test_controllers compiles" || echo "test_controllers FAIL"
python3 -m py_compile tests/test_e2e.py && echo "test_e2e compiles" || echo "test_e2e FAIL"

# If all previous PRPs are implemented, run the full suite:
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30

# Run just the e2e tests:
python3 -m pytest tests/test_e2e.py -v --tb=short

# Check test count
python3 -m pytest tests/ --collect-only -q 2>&1 | tail -5
```

### Success Criteria
- [ ] All 5 test files exist in `tests/`
- [ ] All test files compile without syntax errors (`py_compile`)
- [ ] `conftest.py` provides at least 6 fixtures: `sample_ohlcv_df`, `sample_ohlcv_with_trend`, `sample_ohlcv_with_downtrend`, `mock_db_engine`, `mock_hb_api`, `sample_bot_config`
- [ ] `test_indicators.py` has smoke tests for SniperProX, VZOProX, SpectralAnalysis, UniversalMA, and SignalCombiner
- [ ] `test_data_pipeline.py` tests TSDB write/read, Polygon updater, and YAML config loading
- [ ] `test_controllers.py` tests all 3 controllers, signal validation, config validation, and controller registry
- [ ] `test_e2e.py` tests full pipeline: data -> indicator -> signal -> controller -> deploy
- [ ] All signals validated as integers in {-1, 0, 1}
- [ ] No test requires live services (all mocked)
- [ ] Tests use fixed random seed for reproducibility
- [ ] Total test count is at least 20 across all files
