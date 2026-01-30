# UpTrade — Project Brief

## What
AI-powered crypto trading platform that combines VectorBT Pro's analytical engine with Hummingbot's execution engine, backed by TimescaleDB and Polygon.io.

## Why
- Custom Numba-accelerated indicators (34 MA types, SniperProX, VZO, Spectral cycles, Astro) need a live execution layer
- Hummingbot V2 provides modular Controllers for directional trading on CEX + DEX
- TimescaleDB gives persistent, fast time-series storage with automatic rollups
- MCP integration allows AI agents to orchestrate the entire platform

## Core Components
1. **Data Pipeline:** Polygon.io → TimescaleDB (hypertables + continuous aggregates)
2. **Indicator Engine:** VBT Pro IndicatorFactory indicators with @njit kernels
3. **Signal System:** Configurable combiner (AND/OR/WEIGHTED) across indicators
4. **Execution Bridge:** Hummingbot V2 Controllers consuming VBT signals
5. **Bot Management:** YAML-based config per indicator/pair/exchange/timeframe
6. **DEX Support:** Gateway for Uniswap, Jupiter, Hyperliquid, dYdX
7. **Dashboard:** Streamlit with bot monitoring, signal viz, cycle heatmap
8. **MCP:** Hummingbot MCP for AI-driven bot orchestration

## Key Design Decisions
- **Granular deployment:** Each bot = 1 indicator + 1 pair + 1 exchange + 1 timeframe
- **VBT for analysis, Hummingbot for execution:** Don't reinvent either
- **Docker Compose:** Single `docker-compose up` for entire stack
- **YAML configs:** Human-readable, versionable bot configurations
- **Adaptive cycles:** SpectralAnalysis dominant cycle feeds indicator lengths
