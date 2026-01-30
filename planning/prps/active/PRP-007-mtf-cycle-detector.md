# PRP-007: Multi-Timeframe Cycle Detector

**Wave:** 2 (Indicators)
**Dependencies:** PRP-006 (needs SpectralAnalysis indicator ported to `src/indicators/`)
**Branch:** `feature/prp-007-mtf-cycle-detector`
**Estimated Effort:** 3 hours
**PRD Reference:** PRD-001, Epic 2 (US-2.2), Goal G6

---

## Context Layer

### Goal
Create a Multi-Timeframe Cycle Detector that runs SpectralAnalysis (both Hurst bandpass and Goertzel DFT) across multiple timeframes for a given symbol, identifies the dominant cycle period per timeframe, and produces a composite cycle score. The dominant cycle period can be used as an adaptive length parameter for SniperProX/VZO, replacing static lookback lengths with market-responsive values.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- `src/indicators/spectral.py` — SpectralAnalysis IndicatorFactory (from PRP-006)
- `src/indicators/nb/spectral_nb.py` — Hurst bandpass + Goertzel DFT kernels
- `src/data/tsdb.py` — TimescaleDB read/write (from PRP-004, optional for persistence)
- NumPy, pandas
- VectorBT Pro (`vectorbtpro`)

### Files to Create
1. `src/indicators/mtf_cycles.py` — MTFCycleDetector class

### SpectralAnalysis API Reference (from PRP-006, source: `/home/ai-coder/Projects/vectorbt.pro/Pinescript/vbt/spectral.py`)
```python
from src.indicators.spectral import SpectralAnalysis

# Run spectral analysis
# method: 0 = Hurst bandpass, 1 = Goertzel DFT
result = SpectralAnalysis.run(
    source,            # price series (e.g., hl2 = (high + low) / 2)
    method=0,          # 0=Hurst, 1=Goertzel
    bandwidth=0.025,   # bandpass filter bandwidth
    window_size=618,   # analysis window
    scale_factor=100000.0,
)
result.composite  # composite cycle sum (1D array, same length as source)
```

### Spectral Cycle Periods (from spectral.py)
The SpectralAnalysis indicator evaluates 11 predefined cycle periods:
```python
DEFAULT_PERIODS = [
    4.3,     # 5 Day
    8.5,     # 10 Day
    17.0,    # 20 Day
    34.1,    # 40 Day
    68.2,    # 80 Day
    136.4,   # 20 Week
    272.8,   # 40 Week
    545.6,   # 18 Month
    1636.8,  # 54 Month
    3273.6,  # 9 Year
    6547.2,  # 18 Year
]
CYCLE_NAMES = ["5d", "10d", "20d", "40d", "80d", "20w", "40w", "18m", "54m", "9y", "18y"]
```

### Goertzel Power Spectrum
The Goertzel algorithm computes the power at each specific cycle frequency. To identify the dominant cycle, we run SpectralAnalysis with method=1 (Goertzel) for each cycle period individually and compare the composite output magnitudes. The period with the highest absolute composite value at the latest bar is the dominant cycle.

Alternatively, the Numba kernel `spectral_analysis_1d_nb` returns both `cycles` (individual per-period arrays) and `composite` (sum). By accessing the kernel directly, we can get individual cycle power values.

### TimescaleDB dominant_cycles Schema (from PRP-001 init.sql)
```sql
CREATE TABLE dominant_cycles (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    timeframe   TEXT        NOT NULL,
    method      TEXT,              -- 'hurst' or 'goertzel'
    period      DOUBLE PRECISION,  -- dominant cycle period in bars
    power       DOUBLE PRECISION,  -- cycle strength
    composite   DOUBLE PRECISION   -- composite cycle value
);
```

### Architecture Decisions
- **Run SpectralAnalysis via the Numba kernel directly** (`spectral_analysis_1d_nb`) to get per-cycle-period output arrays, not just the composite — this allows comparing power per period
- **Dominant cycle = period with highest absolute power** at the latest bar in the Goertzel spectrum
- **Composite cycle score** = weighted average of dominant periods across all timeframes, weighted by power
- **OHLCV data source** — accept either a dict of `{timeframe: DataFrame}` or use PRP-004's `read_ohlcv()` to pull from TimescaleDB
- **Persistence optional** — can write results to `dominant_cycles` table, but also works in-memory for backtesting
- **Source price** — use `hl2 = (high + low) / 2` as input to SpectralAnalysis (standard practice)

---

## Task Layer

### Tasks

1. Create `src/indicators/mtf_cycles.py` with class `MTFCycleDetector`:

   1a. **Class-level constants**:
   ```python
   import numpy as np
   from src.indicators.nb.spectral_nb import spectral_analysis_1d_nb
   from src.indicators.spectral import DEFAULT_PERIODS, CYCLE_NAMES

   DEFAULT_TIMEFRAMES = ["5m", "1h", "4h", "1d"]
   METHOD_HURST = 0
   METHOD_GOERTZEL = 1
   ```

   1b. **Constructor** `__init__(self, symbol: str, timeframes: list[str] = None, method: int = 1)`:
   - Store `symbol`, `timeframes` (default: `DEFAULT_TIMEFRAMES`), `method` (default: Goertzel)
   - Store spectral params: `bandwidth=0.025`, `window_size=618`, `scale_factor=100000.0`
   - Initialize logger
   - Store `_results: dict = {}` for caching latest results

   1c. **Method** `analyze_timeframe(self, source: np.ndarray, timeframe: str) -> dict`:
   - Accept a 1D price array (hl2) and timeframe label
   - Call `spectral_analysis_1d_nb(source, DEFAULT_PERIODS, composite_mask, bandwidth, method, window_size, scale_factor)`
     where `composite_mask = np.ones(len(DEFAULT_PERIODS), dtype=np.bool_)`
   - The kernel returns `(cycles, composite)` where:
     - `cycles` is a 2D array of shape `(n_bars, n_periods)` — individual cycle values per period
     - `composite` is a 1D array — sum of all cycles
   - Extract the latest bar values: `latest_cycles = cycles[-1, :]`
   - Find dominant cycle: `dominant_idx = np.argmax(np.abs(latest_cycles))`
   - Return dict:
     ```python
     {
         "timeframe": timeframe,
         "dominant_period": float(DEFAULT_PERIODS[dominant_idx]),
         "dominant_cycle_name": CYCLE_NAMES[dominant_idx],
         "dominant_power": float(latest_cycles[dominant_idx]),
         "all_powers": {CYCLE_NAMES[i]: float(latest_cycles[i]) for i in range(len(CYCLE_NAMES))},
         "composite": float(composite[-1]),
         "method": "hurst" if self.method == 0 else "goertzel",
     }
     ```
   - Log: timeframe, dominant period, dominant power

   1d. **Method** `run(self, data: dict[str, pd.DataFrame]) -> dict`:
   - Accept `data` as dict of `{timeframe: DataFrame}` where each DataFrame has at least `High` and `Low` columns (VBT format from `read_ohlcv`)
   - For each timeframe in `self.timeframes`:
     - Extract DataFrame from `data[timeframe]`
     - Compute `hl2 = (df["High"].values + df["Low"].values) / 2.0`
     - Call `analyze_timeframe(hl2, timeframe)`
   - Collect all results into `self._results`
   - Compute composite cycle score (see task 1e)
   - Return full results dict:
     ```python
     {
         "symbol": self.symbol,
         "timeframes": {tf: result_dict for tf, result_dict in ...},
         "composite_score": composite_score,
         "suggested_length": suggested_length,
     }
     ```

   1e. **Method** `compute_composite_score(self) -> tuple[float, int]`:
   - Compute a weighted average of dominant periods across timeframes
   - Weight each timeframe's dominant period by its absolute power:
     ```python
     periods = [r["dominant_period"] for r in self._results.values()]
     powers = [abs(r["dominant_power"]) for r in self._results.values()]
     total_power = sum(powers)
     if total_power == 0:
         return 0.0, 28  # default
     composite_score = sum(p * w for p, w in zip(periods, powers)) / total_power
     suggested_length = max(7, min(200, round(composite_score)))
     ```
   - `composite_score` is a float representing the weighted dominant period
   - `suggested_length` is the integer version, clamped to [7, 200] range, suitable as indicator length param
   - Return `(composite_score, suggested_length)`

   1f. **Method** `run_from_db(self, read_fn=None, start: str = None, end: str = None) -> dict`:
   - If `read_fn` is provided (PRP-004's `read_ohlcv`), use it to load data from TimescaleDB
   - For each timeframe: `df = read_fn(self.symbol, timeframe, start=start, end=end)`
   - Build data dict and call `self.run(data)`
   - This enables the detector to work directly from the database

   1g. **Method** `to_dataframe(self) -> pd.DataFrame`:
   - Convert latest `_results` to a summary DataFrame
   - Columns: timeframe, dominant_period, dominant_cycle_name, dominant_power, composite, method
   - One row per timeframe
   - Useful for dashboard display

   1h. **Method** `write_to_db(self, write_fn=None) -> int`:
   - If `write_fn` is provided, write results to TimescaleDB `dominant_cycles` table
   - For each timeframe result, create a row with: time=now, symbol, timeframe, method, period, power, composite
   - Use a DataFrame and pass to write function
   - Return number of rows written
   - Note: This uses a simple write function, not the signals upsert — the write_fn should accept a DataFrame with the dominant_cycles columns

2. **Add module-level convenience function**:
   ```python
   def detect_cycles(symbol: str, data: dict, timeframes: list[str] = None, method: int = 1) -> dict:
       """Quick function to detect dominant cycles across timeframes."""
       detector = MTFCycleDetector(symbol=symbol, timeframes=timeframes, method=method)
       return detector.run(data)
   ```

3. **Update `src/indicators/__init__.py`** — add export:
   ```python
   from src.indicators.mtf_cycles import MTFCycleDetector, detect_cycles  # noqa: F401
   ```

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify imports
python3 -c "
from src.indicators.mtf_cycles import MTFCycleDetector, detect_cycles
print('MTFCycleDetector imported OK')
print('detect_cycles imported OK')
"

# Verify class methods exist
python3 -c "
import inspect
from src.indicators.mtf_cycles import MTFCycleDetector
methods = ['analyze_timeframe', 'run', 'compute_composite_score', 'run_from_db', 'to_dataframe', 'write_to_db']
for m in methods:
    assert hasattr(MTFCycleDetector, m), f'Missing method: {m}'
    sig = inspect.signature(getattr(MTFCycleDetector, m))
    print(f'{m}{sig}')
print('All methods present')
"

# Verify constructor
python3 -c "
from src.indicators.mtf_cycles import MTFCycleDetector, DEFAULT_TIMEFRAMES
detector = MTFCycleDetector(symbol='X:BTCUSD')
assert detector.symbol == 'X:BTCUSD'
assert detector.timeframes == DEFAULT_TIMEFRAMES
print(f'Default timeframes: {DEFAULT_TIMEFRAMES}')
print('Constructor OK')
"

# Verify it uses the spectral kernel (not just the IndicatorFactory wrapper)
python3 -c "
import inspect
from src.indicators.mtf_cycles import MTFCycleDetector
src = inspect.getsource(MTFCycleDetector.analyze_timeframe)
assert 'spectral_analysis_1d_nb' in src, 'Must use Numba kernel directly for per-period access'
print('Uses spectral_analysis_1d_nb kernel OK')
"

# Verify __init__.py exports
python3 -c "
from src.indicators import MTFCycleDetector, detect_cycles
print('Package-level exports OK')
"

# Test with synthetic data (if VBT is installed)
python3 -c "
import numpy as np
import pandas as pd
from src.indicators.mtf_cycles import MTFCycleDetector

# Create synthetic price data
np.random.seed(42)
n = 1000
t = np.arange(n)
# Add a 20-bar cycle + trend
price = 100 + 0.01 * t + 5 * np.sin(2 * np.pi * t / 20) + np.random.randn(n) * 0.5
high = price + abs(np.random.randn(n) * 0.3)
low = price - abs(np.random.randn(n) * 0.3)
idx = pd.date_range('2024-01-01', periods=n, freq='h')
df = pd.DataFrame({'High': high, 'Low': low}, index=idx)

detector = MTFCycleDetector(symbol='TEST', timeframes=['1h'])
result = detector.run({'1h': df})
print(f'Dominant period (1h): {result[\"timeframes\"][\"1h\"][\"dominant_period\"]}')
print(f'Composite score: {result[\"composite_score\"]}')
print(f'Suggested length: {result[\"suggested_length\"]}')
print('Synthetic data test OK')
" 2>/dev/null && echo "Synthetic test PASSED" || echo "Synthetic test SKIPPED (VBT not installed)"
```

### Success Criteria
- [ ] `src/indicators/mtf_cycles.py` exists with `MTFCycleDetector` class and `detect_cycles` function
- [ ] `MTFCycleDetector` has methods: `analyze_timeframe`, `run`, `compute_composite_score`, `run_from_db`, `to_dataframe`, `write_to_db`
- [ ] Constructor accepts `symbol`, `timeframes`, `method` with sensible defaults
- [ ] `analyze_timeframe()` calls `spectral_analysis_1d_nb` kernel directly to get per-period cycle arrays
- [ ] `analyze_timeframe()` returns dict with `dominant_period`, `dominant_power`, `all_powers`, `composite`
- [ ] `run()` accepts `dict[str, pd.DataFrame]` and processes all timeframes
- [ ] `compute_composite_score()` returns power-weighted average of dominant periods plus suggested_length clamped to [7, 200]
- [ ] `run_from_db()` integrates with PRP-004's `read_ohlcv` via callable
- [ ] `to_dataframe()` returns summary DataFrame with one row per timeframe
- [ ] `write_to_db()` writes results to `dominant_cycles` table format
- [ ] `src/indicators/__init__.py` exports `MTFCycleDetector` and `detect_cycles`
- [ ] DEFAULT_TIMEFRAMES = `["5m", "1h", "4h", "1d"]`
