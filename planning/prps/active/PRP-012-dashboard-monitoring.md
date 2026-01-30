# PRP-012: Dashboard — Bot Monitoring

**Wave:** 4 (Dashboard)
**Dependencies:** PRP-010 (bot deployment), PRP-004 (TSDB read)
**Branch:** `feature/prp-012-dashboard-monitoring`
**Estimated Effort:** 4 hours
**PRD Reference:** PRD-001, Epic 5 (US-5.1, US-5.3)

---

## Context Layer

### Goal
Build a Streamlit-based dashboard for monitoring live bot status, P&L, active positions, and signal visualization. The dashboard reads bot status from the Hummingbot API and market data / indicator signals from TimescaleDB. It auto-refreshes every 30 seconds and provides interactive Plotly charts with OHLCV candlesticks and indicator overlays.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- Streamlit (latest) — dashboard framework
- Plotly (with plotly.graph_objects) — interactive charts
- pandas — data manipulation
- httpx — async HTTP client for Hummingbot API
- psycopg2 / SQLAlchemy — TimescaleDB reads (via `src/data/` from PRP-004)
- Docker — dashboard runs as a container (Dockerfile.dashboard)

### Files to Create
1. `src/dashboard/app.py` — Main Streamlit app entry point (multi-page setup)
2. `src/dashboard/pages/01_bot_overview.py` — Bot status, P&L, active positions page
3. `src/dashboard/pages/02_signals.py` — Signal visualization with OHLCV + indicator overlays
4. `src/dashboard/components/__init__.py` — Components package init
5. `src/dashboard/components/charts.py` — Reusable chart components (candlestick, signal markers, indicator lines)
6. `src/dashboard/components/bot_cards.py` — Bot status card components
7. `docker/Dockerfile.dashboard` — Dashboard Docker image

### Architecture Decisions
- **Multi-page Streamlit app:** `app.py` is the entry point that configures the sidebar and page navigation. Each page is a separate file in `pages/`.
- **Auto-refresh:** Use `st.empty()` + `time.sleep(30)` + `st.rerun()` pattern, or Streamlit's built-in `st_autorefresh` component for 30-second refresh.
- **Data sources:**
  - Bot status: Hummingbot API (`GET /bot-orchestration/status`) via `BotDeployer.list_bots()` from PRP-010
  - Market data: TimescaleDB via `src/data/tsdb_reader.py` from PRP-004
  - Indicator signals: `indicator_signals` table in TimescaleDB
  - Bot performance: `bot_performance` table in TimescaleDB
- **Chart library:** Plotly `graph_objects` for candlestick charts (not `plotly.express`) to allow layered overlays.
- **Responsive layout:** Streamlit columns for side-by-side bot cards, full-width for charts.
- **Docker image:** Based on `python:3.11-slim`, installs only dashboard dependencies (streamlit, plotly, httpx, psycopg2-binary, pandas), runs `streamlit run src/dashboard/app.py --server.port=8501`.
- **No authentication** in v1 (single-operator system per PRD non-goals).
- **Color scheme:** Green for profit/long signals, red for loss/short signals, gray for neutral.

---

## Task Layer

### Tasks

1. Create `src/dashboard/app.py`:
   - Configure Streamlit page: `st.set_page_config(page_title="UpTrade Dashboard", page_icon="chart_with_upwards_trend", layout="wide")`
   - Sidebar with:
     - UpTrade logo/title
     - Connection status indicators (TimescaleDB, Hummingbot API)
     - Refresh interval selector (10s, 30s, 60s, manual)
     - Symbol filter dropdown (populated from DB)
   - Main content area shows page navigation (Streamlit native multi-page)
   - Initialize shared state in `st.session_state`:
     - `db_connection` — SQLAlchemy engine (from Settings)
     - `hb_api_url` — Hummingbot API URL
     - `selected_symbol` — current symbol filter
     - `refresh_interval` — current refresh interval
   - Connection check on startup: ping TimescaleDB and Hummingbot API, show status in sidebar

2. Create `src/dashboard/pages/01_bot_overview.py`:
   - **Bot Status Cards** (top section):
     - Fetch active bots from Hummingbot API (`GET /bot-orchestration/status`)
     - For each bot, display a card with:
       - Bot name, controller type, trading pair, exchange
       - Status (running/stopped/error) with colored indicator
       - Current P&L (from `bot_performance` table, latest entry)
       - Number of active positions
       - Uptime
     - Use `st.columns()` to display 3 cards per row
   - **P&L Summary** (middle section):
     - Aggregate P&L across all bots (line chart over time from `bot_performance`)
     - Total trades, win rate, max drawdown
     - Time period selector (1h, 4h, 24h, 7d, 30d)
   - **Active Positions Table** (bottom section):
     - Table with: bot_name, symbol, side (long/short), entry_price, current_price, unrealized_pnl, duration
     - Color-coded P&L cells (green positive, red negative)
   - Auto-refresh using `st_autorefresh(interval=refresh_interval * 1000)`

3. Create `src/dashboard/pages/02_signals.py`:
   - **Symbol/Timeframe Selector** (top):
     - Dropdown for symbol (from `SELECT DISTINCT symbol FROM ohlcv`)
     - Dropdown for timeframe (1m, 5m, 1h, 4h, 1d)
     - Dropdown for indicator (SniperProX, VZOProX, SpectralAnalysis, All)
     - Number of candles slider (50-500, default 200)
   - **OHLCV Candlestick Chart** (main):
     - Plotly candlestick chart with volume bars below
     - Overlay indicator signals as markers:
       - Green up-triangle for buy signal (signal=1)
       - Red down-triangle for sell signal (signal=-1)
     - Overlay indicator value as line (secondary y-axis)
   - **Signal History Table** (bottom):
     - Recent signals from `indicator_signals` table
     - Columns: time, symbol, indicator, signal, value
     - Filterable by indicator type
   - Data fetched from TimescaleDB:
     - OHLCV from `ohlcv` table (or continuous aggregates for higher timeframes)
     - Signals from `indicator_signals` table

4. Create `src/dashboard/components/charts.py`:
   - `create_candlestick_chart(df: pd.DataFrame, title: str = "") -> go.Figure`:
     - Takes DataFrame with columns: time, open, high, low, close, volume
     - Returns Plotly figure with candlestick + volume bar subplot
     - Configurable colors (green/red for up/down candles)
   - `add_signal_markers(fig: go.Figure, signals_df: pd.DataFrame) -> go.Figure`:
     - Adds buy/sell markers to existing candlestick chart
     - signals_df has columns: time, signal (1/-1)
     - Buy: green triangle-up at low price - offset
     - Sell: red triangle-down at high price + offset
   - `add_indicator_overlay(fig: go.Figure, df: pd.DataFrame, name: str, color: str = "blue") -> go.Figure`:
     - Adds indicator line on secondary y-axis
     - df has columns: time, value
   - `create_pnl_chart(df: pd.DataFrame) -> go.Figure`:
     - Cumulative P&L line chart
     - Green fill when positive, red fill when negative

5. Create `src/dashboard/components/bot_cards.py`:
   - `render_bot_card(bot_info: dict)`:
     - Renders a Streamlit container with bot status info
     - Uses `st.metric()` for P&L with delta
     - Color-coded status badge
   - `render_bot_grid(bots: list[dict], cols: int = 3)`:
     - Renders bot cards in a grid layout using `st.columns()`

6. Create `src/dashboard/components/__init__.py`:
   - Export chart and card component functions

7. Create `docker/Dockerfile.dashboard`:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY pyproject.toml .
   RUN pip install --no-cache-dir streamlit plotly httpx psycopg2-binary pandas sqlalchemy pydantic pydantic-settings python-dotenv
   COPY src/ src/
   EXPOSE 8501
   HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1
   ENTRYPOINT ["streamlit", "run", "src/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
   ```

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify all files exist
test -f src/dashboard/app.py && echo "OK: app" || echo "FAIL: app"
test -f src/dashboard/pages/01_bot_overview.py && echo "OK: overview" || echo "FAIL: overview"
test -f src/dashboard/pages/02_signals.py && echo "OK: signals" || echo "FAIL: signals"
test -f src/dashboard/components/__init__.py && echo "OK: components init" || echo "FAIL: components init"
test -f src/dashboard/components/charts.py && echo "OK: charts" || echo "FAIL: charts"
test -f src/dashboard/components/bot_cards.py && echo "OK: bot_cards" || echo "FAIL: bot_cards"
test -f docker/Dockerfile.dashboard && echo "OK: Dockerfile" || echo "FAIL: Dockerfile"

# Verify imports (without Streamlit running)
python3 -c "from src.dashboard.components.charts import create_candlestick_chart, add_signal_markers, add_indicator_overlay, create_pnl_chart; print('Charts OK')"
python3 -c "from src.dashboard.components.bot_cards import render_bot_card, render_bot_grid; print('Bot cards OK')"

# Verify chart component works with sample data
python3 -c "
import pandas as pd
import numpy as np
from src.dashboard.components.charts import create_candlestick_chart, add_signal_markers

# Generate sample OHLCV data
dates = pd.date_range('2024-01-01', periods=100, freq='1h')
df = pd.DataFrame({
    'time': dates,
    'open': np.random.uniform(40000, 45000, 100),
    'high': np.random.uniform(45000, 47000, 100),
    'low': np.random.uniform(38000, 40000, 100),
    'close': np.random.uniform(40000, 45000, 100),
    'volume': np.random.uniform(100, 1000, 100),
})
fig = create_candlestick_chart(df, title='Test Chart')
print(f'Chart created with {len(fig.data)} traces')

# Add signal markers
signals_df = pd.DataFrame({
    'time': dates[::10],
    'signal': [1, -1, 1, -1, 1, -1, 1, -1, 1, -1],
})
fig = add_signal_markers(fig, signals_df)
print(f'Chart with signals has {len(fig.data)} traces')
"

# Verify Dockerfile syntax
docker build --check -f docker/Dockerfile.dashboard . 2>/dev/null || python3 -c "
content = open('docker/Dockerfile.dashboard').read()
assert 'FROM python' in content
assert 'streamlit' in content
assert '8501' in content
print('Dockerfile looks valid')
"
```

### Success Criteria
- [ ] All 7 files exist in correct locations
- [ ] `app.py` configures multi-page Streamlit app with sidebar navigation
- [ ] `01_bot_overview.py` displays bot cards, P&L chart, and positions table
- [ ] `02_signals.py` displays OHLCV candlestick chart with indicator overlays and signal markers
- [ ] `charts.py` exports 4 reusable chart functions (candlestick, signals, indicator, P&L)
- [ ] `bot_cards.py` exports bot card rendering functions
- [ ] `Dockerfile.dashboard` builds successfully with all dependencies
- [ ] Charts render correctly with sample data (no import errors)
- [ ] Auto-refresh configured at 30-second intervals
- [ ] Dashboard reads from both Hummingbot API (bot status) and TimescaleDB (market data, signals)
