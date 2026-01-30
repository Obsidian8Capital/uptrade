# PRP-013: Dashboard — Cycle Heatmap

**Wave:** 4 (Dashboard)
**Dependencies:** PRP-007 (MTF cycle detector), PRP-012 (dashboard base)
**Branch:** `feature/prp-013-dashboard-cycles`
**Estimated Effort:** 3 hours
**PRD Reference:** PRD-001, Epic 5 (US-5.2)

---

## Context Layer

### Goal
Create a Streamlit dashboard page that displays a dominant cycle heatmap across multiple timeframes. The heatmap visualizes cycle power (Goertzel magnitude) for each cycle period across timeframes, highlights the dominant cycle per timeframe, and overlays a composite cycle waveform on a price chart. This page provides traders with visual insight into which market cycles are currently active and how they relate to price action.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- Streamlit — page within existing dashboard (PRP-012)
- Plotly (`graph_objects` and `express`) — heatmap and overlay charts
- pandas — data manipulation
- numpy — numerical computations for composite waveform rendering
- TimescaleDB — reads from `dominant_cycles` table (created in PRP-001, populated by PRP-007)
- SQLAlchemy — database queries via `src/data/` from PRP-004

### Files to Create
1. `src/dashboard/pages/03_cycles.py` — Dominant cycle heatmap page

### Existing Files Used (Read Only)
- `src/data/tsdb_reader.py` (PRP-004) — TimescaleDB read functions
- `src/dashboard/app.py` (PRP-012) — Main dashboard app (this page auto-registers)
- `src/dashboard/components/charts.py` (PRP-012) — Reusable chart components
- `src/indicators/spectral.py` (PRP-006) — SpectralAnalysis indicator (for reference on cycle data format)

### Architecture Decisions
- **Heatmap axes:**
  - X-axis: Timeframe (5m, 1h, 4h, 1d)
  - Y-axis: Cycle period in bars (mapped to approximate days: 4.3 days to 6547 days, logarithmic scale)
  - Color: Cycle power (Goertzel magnitude) — hot (red/yellow) = strong cycle, cool (blue/purple) = weak
- **Data source:** `dominant_cycles` table in TimescaleDB with schema:
  ```sql
  time TIMESTAMPTZ, symbol TEXT, timeframe TEXT, method TEXT,
  period DOUBLE PRECISION, power DOUBLE PRECISION, composite DOUBLE PRECISION
  ```
- **Dominant cycle highlighting:** The strongest cycle per timeframe (highest power) is highlighted with a white border/marker on the heatmap.
- **Composite waveform:** A reconstructed sine wave from the top N dominant cycles, overlaid on the OHLCV price chart. This shows the predicted cyclic component of price.
- **Update frequency:** Refreshes on each candle close event, which in practice means the dashboard polls on its auto-refresh interval (30s from PRP-012) and the data updates when PRP-007's cycle detector writes new results.
- **Cycle period display:** Show both bar count and approximate calendar duration (e.g., "50 bars (2.1 days on 1h)").
- **Goertzel spectrum:** For each timeframe, query the last computation's full spectrum (all periods tested), not just the dominant one. This requires the cycle detector (PRP-007) to store per-period power values, or we compute a summary from stored dominant cycles.
- **Fallback:** If no cycle data exists for a symbol/timeframe combo, show "No data" placeholder in that heatmap cell.

### Cycle Period Reference (from PRD)
| Timeframe | Bars | Approximate Days |
|-----------|------|-----------------|
| 5m | 1,234 | 4.3 days |
| 1h | 157 | 6.5 days |
| 4h | 1,637 | 273 days |
| 1d | 6,547 | 6,547 days (~18 years) |

These represent the maximum detectable cycle period per timeframe given typical data availability.

---

## Task Layer

### Tasks

1. Create `src/dashboard/pages/03_cycles.py`:

   **Section A: Page Header and Controls**
   - Page title: "Dominant Cycle Analysis"
   - Controls row:
     - Symbol selector dropdown (from `SELECT DISTINCT symbol FROM dominant_cycles`)
     - Method selector: "goertzel" or "hurst"
     - Time range: last 24h, 7d, 30d (how far back to query cycle data)
     - Number of candles for price chart: slider 100-1000, default 500

   **Section B: Cycle Heatmap**
   - Query `dominant_cycles` table for selected symbol, method, and time range:
     ```sql
     SELECT timeframe, period, power, time
     FROM dominant_cycles
     WHERE symbol = :symbol AND method = :method AND time > :start_time
     ORDER BY time DESC
     ```
   - Group by timeframe, aggregate power per period bucket (use logarithmic period bins)
   - Build heatmap matrix:
     - Rows: period bins (logarithmic scale, e.g., [5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, ...] — Fibonacci-like spacing)
     - Columns: timeframes ["5m", "1h", "4h", "1d"]
     - Values: average cycle power for that period bucket in that timeframe
   - Render with `plotly.graph_objects.Heatmap`:
     - Colorscale: "Hot" (or "Inferno" — dark blue to yellow to red)
     - Y-axis labels show both bar count and approximate calendar duration
     - Hover text shows: timeframe, period, power, dominant (yes/no)
   - Highlight dominant cycle per timeframe:
     - Find max power cell per column
     - Add annotation marker (star or border) on dominant cells
   - Display dominant cycle summary below heatmap:
     - Table: | Timeframe | Dominant Period | Power | Calendar Duration |

   **Section C: Composite Cycle Waveform on Price Chart**
   - Fetch OHLCV data for selected symbol (use highest available timeframe, e.g., 1h)
   - Fetch latest dominant cycles for each timeframe
   - Reconstruct composite waveform:
     - For each dominant cycle, create a sine wave: `A * sin(2 * pi * t / period + phase)`
     - Where A = normalized power, period = dominant period in bars, phase estimated from data
     - Sum all sine waves to get composite
   - Overlay composite waveform on OHLCV candlestick chart:
     - Use `create_candlestick_chart()` from PRP-012 components
     - Add composite as a line on secondary y-axis (or normalized to price range)
     - Color: cyan/teal to stand out against red/green candles
   - Add annotations for cycle peaks and troughs (vertical lines or markers)

   **Section D: Cycle Statistics**
   - Summary metrics (using `st.metric()`):
     - Shortest active cycle (period with highest power across all timeframes)
     - Longest active cycle
     - Cycle convergence score (how many timeframes agree on similar dominant periods)
     - Current composite direction (up/down based on composite waveform slope)
   - History of dominant cycle changes:
     - Table showing when dominant cycles shifted over the selected time range
     - Columns: time, timeframe, old_period, new_period, power_change

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify file exists
test -f src/dashboard/pages/03_cycles.py && echo "OK: cycles page" || echo "FAIL: cycles page"

# Verify imports work
python3 -c "
# Check that the page module can be imported (Streamlit components will not render outside Streamlit)
import importlib.util
spec = importlib.util.spec_from_file_location('cycles', 'src/dashboard/pages/03_cycles.py')
print('Module spec created OK')
"

# Verify heatmap data processing logic (isolated from Streamlit)
python3 -c "
import pandas as pd
import numpy as np

# Simulate cycle data
np.random.seed(42)
timeframes = ['5m', '1h', '4h', '1d']
periods = [5, 8, 13, 21, 34, 55, 89, 144, 233, 377]
rows = []
for tf in timeframes:
    for p in periods:
        rows.append({'timeframe': tf, 'period': p, 'power': np.random.uniform(0, 1)})
df = pd.DataFrame(rows)

# Pivot to heatmap matrix
matrix = df.pivot(index='period', columns='timeframe', values='power')
matrix = matrix[timeframes]  # ensure column order
print(f'Heatmap matrix shape: {matrix.shape}')
print(f'Timeframes: {list(matrix.columns)}')
print(f'Periods: {list(matrix.index)}')

# Find dominant per timeframe
for tf in timeframes:
    dominant_idx = matrix[tf].idxmax()
    print(f'{tf}: dominant period = {dominant_idx}, power = {matrix[tf][dominant_idx]:.3f}')
print('Heatmap logic OK')
"

# Verify composite waveform generation
python3 -c "
import numpy as np

# Simulate composite cycle waveform
t = np.arange(500)
dominant_cycles = [
    {'period': 21, 'power': 0.8},
    {'period': 55, 'power': 0.6},
    {'period': 144, 'power': 0.4},
]
composite = np.zeros(len(t))
for cycle in dominant_cycles:
    A = cycle['power']
    period = cycle['period']
    composite += A * np.sin(2 * np.pi * t / period)
print(f'Composite waveform: min={composite.min():.2f}, max={composite.max():.2f}, len={len(composite)}')
print('Composite waveform OK')
"
```

### Success Criteria
- [ ] `03_cycles.py` exists in `src/dashboard/pages/`
- [ ] Page displays a heatmap with X=timeframe, Y=cycle period, color=power
- [ ] Heatmap uses logarithmic period bins on Y-axis
- [ ] Dominant cycle per timeframe is highlighted on the heatmap
- [ ] Dominant cycle summary table displayed below heatmap
- [ ] Composite cycle waveform overlaid on OHLCV candlestick chart
- [ ] Composite waveform reconstructed from dominant cycles as sine wave sum
- [ ] Cycle statistics section shows shortest/longest cycles, convergence score, composite direction
- [ ] Data reads from `dominant_cycles` TimescaleDB table
- [ ] Symbol and method selectors functional
- [ ] Graceful handling when no cycle data exists (shows placeholder)
- [ ] Page auto-refreshes with dashboard interval (inherits from PRP-012)
