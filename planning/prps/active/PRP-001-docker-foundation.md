# PRP-001: Docker Foundation & TimescaleDB Schema

**Wave:** 0 (Foundation)
**Dependencies:** None
**Branch:** `feature/prp-001-docker-foundation`
**Estimated Effort:** 2 hours
**PRD Reference:** PRD-001, Epic 6 (US-6.1, US-6.2, US-6.3), Epic 1 (US-1.1)

---

## Context Layer

### Goal
Set up the Docker Compose stack that runs the entire UpTrade platform and initialize the TimescaleDB schema with hypertables, continuous aggregates, and indexes.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- Docker Compose v2
- TimescaleDB (timescale/timescaledb:latest-pg16)
- Hummingbot API (hummingbot/hummingbot-api:latest)
- Hummingbot Gateway (hummingbot/gateway:latest)
- Hummingbot MCP (hummingbot/hummingbot-mcp:latest)
- PostgreSQL 16

### Files to Create
1. `docker/docker-compose.yml` — Full stack compose file
2. `docker/init.sql` — TimescaleDB schema initialization
3. `docker/.env.example` — Environment variable template
4. `docker/healthcheck.sh` — DB health check script
5. `src/__init__.py` — Package init
6. `src/config/settings.py` — Central config loading from env vars
7. `src/config/__init__.py` — Config package init
8. `pyproject.toml` — Python project config with dependencies

### Architecture Decisions
- **Single compose file** with all services (TimescaleDB, HB API, Gateway, MCP, Dashboard placeholder)
- **Named volumes** for data persistence
- **Health checks** on all services
- **Network isolation** — internal network for service-to-service, exposed ports only where needed
- **.env file** for all secrets (API keys, DB creds, exchange creds)
- **TimescaleDB hypertables** for: ohlcv, indicator_signals, bot_performance, dominant_cycles
- **Continuous aggregates** for automatic 1m → 5m → 1h → 1d rollup
- **Compression policies** on ohlcv data older than 7 days
- **Retention policy** configurable via env var (default 365 days for 1m data)

---

## Task Layer

### Tasks

1. Create `docker/docker-compose.yml` with services:
   - `timescaledb` — port 5432, volume mount, healthcheck
   - `hummingbot-api` — port 8000, depends_on timescaledb
   - `hummingbot-gateway` — port 15888, depends_on hummingbot-api
   - `hummingbot-mcp` — depends_on hummingbot-api (no exposed port, stdio transport)
   - `dashboard` — port 8501, depends_on all (placeholder, will be built in PRP-012)
   - Internal network `uptrade-net`
   - Named volumes: `tsdb_data`, `hb_bots`, `hb_certs`

2. Create `docker/init.sql` with:
   - TimescaleDB extension
   - `ohlcv` hypertable with composite index on (symbol, timeframe, time)
   - `indicator_signals` hypertable
   - `bot_performance` hypertable
   - `dominant_cycles` hypertable
   - Continuous aggregates: `ohlcv_5m`, `ohlcv_1h`, `ohlcv_1d` from 1m data
   - Compression policy on ohlcv (compress after 7 days)
   - Helper functions: `upsert_ohlcv()` for conflict-free inserts

3. Create `docker/.env.example` with:
   - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
   - `POLYGON_API_KEY`
   - `HB_API_USER`, `HB_API_PASSWORD`
   - `GW_PASSPHRASE`
   - `EXCHANGE_*` placeholders for exchange API keys

4. Create `src/config/settings.py`:
   - Pydantic `Settings` class loading from `.env`
   - Database URL builder
   - Polygon API config
   - Hummingbot API config

5. Create `pyproject.toml` with dependencies:
   - vectorbtpro, numba, numpy, pandas
   - sqlalchemy, psycopg2-binary
   - polygon-api-client
   - pydantic, pydantic-settings
   - streamlit (optional, dashboard)
   - python-dotenv

---

## Validation Layer

### Commands
```bash
# Syntax check
cd /home/ai-coder/Projects/uptrade
python3 -c "import yaml; yaml.safe_load(open('docker/docker-compose.yml'))" 2>/dev/null || docker compose -f docker/docker-compose.yml config --quiet
cat docker/init.sql | head -5  # verify SQL exists
python3 -c "from src.config.settings import Settings; print('Settings OK')"
```

### Success Criteria
- [ ] `docker compose -f docker/docker-compose.yml config` validates without errors
- [ ] `init.sql` contains CREATE TABLE + create_hypertable for all 4 tables
- [ ] `init.sql` contains CREATE MATERIALIZED VIEW for 3 continuous aggregates
- [ ] `.env.example` documents all required environment variables
- [ ] `settings.py` loads config from env vars with defaults
- [ ] `pyproject.toml` lists all dependencies
- [ ] All files exist in correct locations
