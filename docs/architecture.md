# System Architecture

## System Overview

UpTrade is an AI-powered crypto trading platform that combines VectorBT Pro analytics with Hummingbot execution. Data flows from Polygon.io into TimescaleDB, gets processed by Numba-compiled indicators, and drives automated bot deployments on CEX and DEX venues.

```mermaid
graph TB
    subgraph External
        POLY[Polygon.io API]
        CEX[CEX Exchanges<br/>Binance, OKX, Bybit]
        DEX[DEX Protocols<br/>Uniswap, Jupiter, Hyperliquid]
    end

    subgraph Docker Network
        TSDB[(TimescaleDB)]
        HB_API[Hummingbot API<br/>:8000]
        HB_GW[Hummingbot Gateway<br/>:15888]
        HB_MCP[Hummingbot MCP<br/>stdio]
    end

    subgraph UpTrade Application
        DATA[Data Layer<br/>PolygonClient, DataUpdater]
        IND[Indicator Engine<br/>SniperProX, VZOProX, Spectral]
        CTRL[Controllers<br/>Sniper, VZO, Cycle]
        SIG[Signal Combiner]
        DASH[Dashboard<br/>Streamlit :8501]
        CFG[Config & Deployer]
    end

    subgraph AI Agent
        CLAUDE[Claude / AI Assistant]
    end

    POLY --> DATA
    DATA --> TSDB
    TSDB --> IND
    IND --> SIG
    SIG --> CTRL
    CTRL --> CFG
    CFG --> HB_API
    HB_API --> CEX
    HB_API --> HB_GW
    HB_GW --> DEX
    TSDB --> DASH
    HB_API --> DASH
    CLAUDE --> HB_MCP
    HB_MCP --> HB_API
```

---

## Data Flow

```mermaid
sequenceDiagram
    participant P as Polygon.io
    participant PC as PolygonClient
    participant DB as TimescaleDB
    participant IND as Indicators
    participant SC as SignalCombiner
    participant CTRL as Controller
    participant HB as Hummingbot API
    participant EX as Exchange

    Note over PC,DB: Data Ingestion (continuous)
    PC->>P: Pull OHLCV (incremental)
    P-->>PC: Candle data
    PC->>DB: write_ohlcv() (upsert)
    DB->>DB: Continuous aggregates (5m, 1h, 1d)

    Note over IND,CTRL: Signal Generation (per candle)
    CTRL->>DB: Read latest candles
    DB-->>CTRL: OHLCV DataFrame
    CTRL->>IND: Run SniperProX / VZOProX
    IND-->>CTRL: Signal arrays
    CTRL->>SC: Combine signals
    SC-->>CTRL: Combined direction (1, 0, -1)

    Note over HB,EX: Order Execution
    CTRL->>HB: Deploy V2 script
    HB->>EX: Place order
    EX-->>HB: Fill confirmation
    HB-->>DB: Log performance
```

---

## Component Architecture

### Data Layer (`src/data/`)

| Module | Responsibility |
|--------|---------------|
| `polygon_client.py` | Fetches OHLCV data from Polygon.io via VBT Pro's `PolygonData` |
| `tsdb.py` | TimescaleDB read/write operations (SQLAlchemy) |
| `updater.py` | Continuous polling service with per-timeframe intervals |
| `db.py` | Database connection and session management |

The `DataUpdaterService` runs one async task per symbol/timeframe pair, polling at 80% of the candle duration. On startup, it performs an incremental backfill to fill any gaps.

### Indicator Engine (`src/indicators/`)

| Module | Description |
|--------|-------------|
| `sniper.py` | SniperProX (Fisher transform + DMI/ADX + adaptive zones) |
| `vzo.py` | VZOProX (Volume Zone Oscillator + noise filter) |
| `spectral.py` | Spectral Analysis (Hurst bandpass / Goertzel DFT) |
| `ma_library.py` | Universal MA wrapper (34 types) |
| `mtf_cycles.py` | Multi-timeframe cycle detector |
| `astro_lib.py` | Planetary position calculations |
| `celestial_channels.py` | Planetary longitude to price levels |
| `signals.py` | Simple entry/exit signal generation |
| `backtest.py` | VBT Portfolio backtesting pipeline |
| `optimize.py` | Grid-search parameter optimization |
| `nb/` | Numba-compiled kernels (sniper_nb, vzo_nb, spectral_nb, ma_library_nb, astro_nb) |

All heavy computation lives in `nb/` as `@njit` functions. The parent modules provide VBT `IndicatorFactory` wrappers for pandas/numpy interop.

### Controllers (`src/controllers/`)

| Module | Controller Type | Indicator |
|--------|----------------|-----------|
| `base_vbt_controller.py` | `vbt_base` | Abstract base with data pipeline |
| `sniper_controller.py` | `vbt_sniper` | SniperProX |
| `vzo_controller.py` | `vbt_vzo` | VZOProX |
| `cycle_controller.py` | `vbt_cycle` | SpectralAnalysis |

Controllers implement the Hummingbot V2 `DirectionalTrading` interface. Each controller:
1. Receives candle data from the market data provider
2. Runs its indicator through the Numba-compiled kernel
3. Returns a signal: `1` (long), `-1` (short), `0` (neutral)

### Dashboard (`src/dashboard/`)

| Module | Page | Description |
|--------|------|-------------|
| `app.py` | Home | Landing page with sidebar controls |
| `pages/01_bot_overview.py` | Bot Overview | Live bot statuses, P&L summary |
| `pages/02_signals.py` | Signals | OHLCV charts with indicator overlays |
| `pages/03_cycles.py` | Cycles | Spectral analysis visualization |
| `components/bot_cards.py` | — | Reusable bot status card components |
| `components/charts.py` | — | Plotly chart builders |

### Configuration (`src/config/`)

| Module | Purpose |
|--------|---------|
| `settings.py` | Pydantic settings from environment variables |
| `bot_config.py` | YAML bot deployment config models |
| `deployer.py` | Async HTTP client for Hummingbot V2 REST API |
| `gateway_config.py` | Gateway DEX connector client |
| `examples/` | Sample YAML configs for different strategies |

---

## Database Schema

```mermaid
erDiagram
    ohlcv {
        timestamptz time PK
        text symbol PK
        text timeframe PK
        float8 open
        float8 high
        float8 low
        float8 close
        float8 volume
        float8 vwap
        int trade_count
    }

    indicator_signals {
        timestamptz time PK
        text symbol
        text timeframe
        text indicator
        int signal
        float8 value
        jsonb params
    }

    bot_performance {
        timestamptz time PK
        text bot_name
        text symbol
        text exchange
        float8 pnl
        int trades
        float8 win_rate
        float8 drawdown
        float8 sharpe
    }

    dominant_cycles {
        timestamptz time PK
        text symbol
        text timeframe
        text method
        float8 period
        float8 power
        float8 composite
    }

    ohlcv ||--o{ indicator_signals : "generates"
    ohlcv ||--o{ dominant_cycles : "analyzed by"
    bot_performance ||--o{ ohlcv : "trades on"
```

All four tables are TimescaleDB hypertables with automatic partitioning on the `time` column. Continuous aggregates roll up `ohlcv` from 1m to 5m, 1h, and 1d. The `ohlcv` table has a compression policy that compresses chunks older than 7 days.

---

## Docker Service Map

```mermaid
graph LR
    subgraph uptrade-net
        TSDB[timescaledb<br/>:5432<br/>timescale/timescaledb:latest-pg16]
        API[hummingbot-api<br/>:8000<br/>hummingbot/hummingbot-api:latest]
        GW[hummingbot-gateway<br/>:15888<br/>hummingbot/gateway:latest]
        MCP[hummingbot-mcp<br/>stdio<br/>hummingbot/hummingbot-mcp:latest]
    end

    TSDB -->|healthy| API
    API --> GW
    API --> MCP

    TSDB --- V1[tsdb_data volume]
    GW --- V2[hb_certs volume]
```

**Dependency chain:** `timescaledb` (healthy) -> `hummingbot-api` -> `hummingbot-gateway`, `hummingbot-mcp`

All services use `restart: unless-stopped` and are connected to the `uptrade-net` bridge network.

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Analytics** | VectorBT Pro | Latest | Portfolio backtesting, indicator framework |
| **Computation** | Numba | 0.59+ | JIT-compiled indicator kernels |
| **Data** | NumPy / Pandas | 1.24+ / 2.0+ | Array and DataFrame operations |
| **Database** | TimescaleDB | PG16 | Time-series storage with hypertables |
| **ORM** | SQLAlchemy | 2.0+ | Database access layer |
| **Market Data** | Polygon.io | API v2 | Historical + real-time crypto OHLCV |
| **Execution** | Hummingbot | V2 API | Bot orchestration, order management |
| **DEX Access** | Hummingbot Gateway | Latest | Multi-chain DEX connector |
| **AI Interface** | Hummingbot MCP | Latest | Model Context Protocol server |
| **Dashboard** | Streamlit | 1.30+ | Web monitoring UI |
| **Charts** | Plotly | 5.18+ | Interactive candlestick and signal charts |
| **Config** | Pydantic | 2.0+ | Settings and config validation |
| **HTTP Client** | httpx | 0.25+ | Async API client |
| **Language** | Python | 3.10+ | Application language |
| **Containers** | Docker Compose | v2+ | Service orchestration |
