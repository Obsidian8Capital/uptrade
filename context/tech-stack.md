# UpTrade — Technology Stack

## Core
| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.10+ |
| Acceleration | Numba (@njit) | 0.59+ |
| Data Analysis | VectorBT Pro | Latest |
| Execution | Hummingbot | v2.12+ |
| Database | TimescaleDB | PostgreSQL 16 |
| Data Feed | Polygon.io | REST API |
| Dashboard | Streamlit | 1.30+ |
| Orchestration | MCP (Model Context Protocol) | Via Hummingbot MCP |

## Python Dependencies
| Package | Purpose |
|---------|---------|
| vectorbtpro | Indicators, backtesting, optimization |
| numba | JIT compilation for indicator kernels |
| numpy | Numerical computation |
| pandas | DataFrames |
| sqlalchemy | Database ORM / connection |
| psycopg2-binary | PostgreSQL driver |
| polygon-api-client | Polygon.io data |
| pydantic | Config validation |
| pydantic-settings | Environment loading |
| pyyaml | Bot config files |
| httpx | Async HTTP for Hummingbot API |
| streamlit | Dashboard |
| plotly | Interactive charts |
| pytest | Testing |

## Infrastructure
| Service | Image | Port |
|---------|-------|------|
| TimescaleDB | timescale/timescaledb:latest-pg16 | 5432 |
| Hummingbot API | hummingbot/hummingbot-api:latest | 8000 |
| Hummingbot Gateway | hummingbot/gateway:latest | 15888 |
| Hummingbot MCP | hummingbot/hummingbot-mcp:latest | stdio |
| Dashboard | Custom Dockerfile | 8501 |

## Exchange Support
### CEX (Direct Connectors)
- Binance (spot + perpetual)
- OKX (spot + perpetual)
- Bybit (spot + perpetual)

### DEX (Via Gateway)
- Uniswap V3 (Ethereum, Polygon, Arbitrum)
- Jupiter (Solana)
- Hyperliquid (DEX perpetuals)
- dYdX v4 (Cosmos-based)
