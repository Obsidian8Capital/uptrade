# Deployment Guide

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Docker + Docker Compose | 20.10+ / v2+ | Container orchestration |
| Python | 3.10+ | Local scripts and dashboard |
| Git | 2.x | Version control |
| Polygon.io API Key | Free tier+ | Historical + real-time crypto OHLCV data |
| Hummingbot API credentials | — | Bot orchestration REST API |

Optional:
- Exchange API keys (Binance, OKX, Bybit) for CEX trading
- Gateway passphrase for DEX trading (Uniswap, Jupiter, Hyperliquid)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Obsidian8Capital/uptrade.git
cd uptrade

# 2. Configure environment
cp docker/.env.example docker/.env
# Edit docker/.env with your API keys (see Environment Variables below)

# 3. Start all services
cd docker
docker compose up -d

# 4. Health check
docker compose ps
docker exec uptrade-timescaledb pg_isready -U uptrade

# 5. Open the dashboard (run from project root)
cd ..
pip install -e ".[dashboard]"
streamlit run src/dashboard/app.py
```

The dashboard opens at `http://localhost:8501`.

---

## Environment Variables

All variables are set in `docker/.env`. Copy from `docker/.env.example` and fill in your values.

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `POSTGRES_USER` | `uptrade` | No | TimescaleDB username |
| `POSTGRES_PASSWORD` | `uptrade_dev_password` | **Yes (change in prod)** | TimescaleDB password |
| `POSTGRES_DB` | `uptrade` | No | Database name |
| `POLYGON_API_KEY` | — | **Yes** | Polygon.io API key for market data |
| `HB_API_USER` | `admin` | No | Hummingbot API username |
| `HB_API_PASSWORD` | — | **Yes** | Hummingbot API password |
| `GW_PASSPHRASE` | — | DEX only | Hummingbot Gateway passphrase |
| `BINANCE_API_KEY` | — | CEX only | Binance API key |
| `BINANCE_API_SECRET` | — | CEX only | Binance API secret |
| `OKX_API_KEY` | — | CEX only | OKX API key |
| `OKX_API_SECRET` | — | CEX only | OKX API secret |
| `OKX_PASSPHRASE` | — | CEX only | OKX passphrase |
| `BYBIT_API_KEY` | — | CEX only | Bybit API key |
| `BYBIT_API_SECRET` | — | CEX only | Bybit API secret |

Application-level settings (used by Python code, configured in `src/config/settings.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | DB host (use `timescaledb` inside Docker network) |
| `POSTGRES_PORT` | `5432` | DB port |
| `HB_API_HOST` | `localhost` | Hummingbot API host |
| `HB_API_PORT` | `8000` | Hummingbot API port |
| `GW_HOST` | `localhost` | Gateway host |
| `GW_PORT` | `15888` | Gateway port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DATA_RETENTION_DAYS` | `365` | Data retention period |

---

## Service Ports

| Service | Container Name | Port | Protocol | Description |
|---------|----------------|------|----------|-------------|
| TimescaleDB | `uptrade-timescaledb` | `5432` | PostgreSQL | Time-series database |
| Hummingbot API | `uptrade-hb-api` | `8000` | HTTP/REST | Bot orchestration API |
| Hummingbot Gateway | `uptrade-hb-gateway` | `15888` | HTTPS | DEX connector gateway |
| Hummingbot MCP | `uptrade-hb-mcp` | — (stdio) | MCP/stdio | AI agent interface |
| Dashboard | Local process | `8501` | HTTP | Streamlit monitoring UI |

---

## Data Initialization

### Automatic Schema Setup

The `docker/init.sql` script runs automatically on first database startup. It creates:

- **`ohlcv`** hypertable with continuous aggregates (`ohlcv_5m`, `ohlcv_1h`, `ohlcv_1d`)
- **`indicator_signals`** hypertable for cached indicator output
- **`bot_performance`** hypertable for P&L tracking
- **`dominant_cycles`** hypertable for spectral analysis results
- Compression policy (data older than 7 days is compressed)
- Upsert helper function `upsert_ohlcv()`

### Manual Data Ingestion

After services are running, backfill historical data:

```bash
# Install the package locally
pip install -e .

# Ingest data for a single symbol
python scripts/ingest_data.py --symbol BTC-USDT --timeframe 1h --start 2024-01-01 --end 2024-12-31

# Start the continuous data updater
python scripts/run_updater.py
```

The `DataUpdaterService` polls Polygon.io at 80% of each timeframe's duration (e.g., every 48 seconds for 1m candles) and writes new bars to TimescaleDB.

---

## Exchange Credential Setup

### Binance (CEX)

1. Create API keys at [Binance API Management](https://www.binance.com/en/my/settings/api-management)
2. Enable **Futures** permissions if using perpetual contracts
3. Add to `docker/.env`:
   ```
   BINANCE_API_KEY=your_key
   BINANCE_API_SECRET=your_secret
   ```

### DEX via Hummingbot Gateway

Supported chains and connectors:

| Chain | Network | Connector |
|-------|---------|-----------|
| Ethereum | mainnet | Uniswap |
| Polygon | mainnet | Uniswap |
| Arbitrum | mainnet | Uniswap |
| Solana | mainnet | Jupiter |
| Hyperliquid | mainnet | Hyperliquid |
| dYdX | mainnet | dYdX |

Setup steps:

```bash
# 1. Set Gateway passphrase in docker/.env
GW_PASSPHRASE=your_secure_passphrase

# 2. Start services
docker compose up -d

# 3. Run the Gateway setup script to add wallets
python scripts/setup_gateway.py
```

The `setup_gateway.py` script interacts with the Gateway REST API to register wallets and approve tokens.

---

## Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `pg_isready` fails | TimescaleDB not ready | Wait 30s for startup, check `docker logs uptrade-timescaledb` |
| Polygon data pull returns empty | Invalid API key or symbol | Verify `POLYGON_API_KEY` in `.env`; check symbol format (e.g., `X:BTCUSD`) |
| Hummingbot API connection refused | Service not running or wrong port | `docker compose ps` to check; verify `HB_API_PORT` |
| Gateway SSL errors | Missing certs | Restart gateway container; certs auto-generate on first run |
| Dashboard import errors | Missing dependencies | `pip install -e ".[dashboard]"` |
| Numba compilation slow on first run | Expected behavior | First indicator call triggers JIT compilation; subsequent calls are cached |

### Checking Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f timescaledb
docker compose logs -f hummingbot-api
docker compose logs -f hummingbot-gateway

# Python application logs
tail -f /tmp/updater_health   # Data updater heartbeat
```

### Full Reset

```bash
cd docker

# Stop and remove containers + volumes
docker compose down -v

# Rebuild from scratch
docker compose up -d
```

This destroys all data. The schema will be re-created from `init.sql` on next startup.
