# PRP-015: MCP Orchestration & Deployment Docs

**Wave:** 5 (Integration)
**Dependencies:** All previous PRPs (PRP-001 through PRP-014)
**Branch:** `feature/prp-015-mcp-docs`
**Estimated Effort:** 3.5 hours
**PRD Reference:** PRD-001, Epic 6 (US-6.1, US-6.2), Goal G9

---

## Context Layer

### Goal
Create comprehensive documentation for the UpTrade platform covering deployment, MCP workflow orchestration, indicator reference, and system architecture. Also create the `.mcp.json` configuration file that enables AI agents to interact with Hummingbot MCP for natural-language bot management. Update the project `README.md` with a complete overview and quickstart guide.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- Markdown — documentation format
- Mermaid — architecture diagrams (rendered by GitHub)
- MCP (Model Context Protocol) — AI agent orchestration
- Hummingbot MCP server — provides tools for bot management via MCP

### Files to Create
1. `docs/deployment.md` — Full deployment guide
2. `docs/mcp-workflows.md` — MCP workflow examples
3. `docs/indicators.md` — Indicator reference documentation
4. `docs/architecture.md` — System architecture with Mermaid diagrams
5. `.mcp.json` — MCP server configuration for Hummingbot MCP

### Files to Update
6. `README.md` — Project overview, quickstart, links to docs

### Architecture Decisions
- **Documentation in `docs/` directory** rather than a wiki — keeps docs versioned with code.
- **Mermaid diagrams** for architecture — renders natively on GitHub, no image files to maintain.
- **MCP configuration** uses the standard `.mcp.json` format compatible with Claude Code and other MCP clients.
- **Indicator reference** documents all parameters with defaults, ranges, and usage examples — serves as both human and AI agent reference.
- **Deployment guide** assumes the reader starts from a fresh Ubuntu/macOS machine with Docker installed.

---

## Task Layer

### Tasks

1. Create `docs/deployment.md`:
   - **Prerequisites section:**
     - Docker and Docker Compose v2 installed
     - Python 3.11+ (for local development only; Docker handles runtime)
     - Git
     - API keys: Polygon.io (free tier minimum), exchange API keys for trading
   - **Quick Start (5 steps):**
     1. `git clone https://github.com/Obsidian8Capital/uptrade.git && cd uptrade`
     2. `cp docker/.env.example docker/.env` and fill in API keys
     3. `docker compose -f docker/docker-compose.yml up -d`
     4. Wait for health checks to pass: `docker compose -f docker/docker-compose.yml ps`
     5. Open dashboard: `http://localhost:8501`
   - **Environment Variables Reference:**
     - Table of ALL env vars from `.env.example` with: name, description, required (yes/no), default, example
     - Grouped by: Database, Polygon, Hummingbot API, Gateway, Exchange API keys
   - **Service Ports:**
     - Table: service, internal port, external port, purpose
     - TimescaleDB: 5432, Hummingbot API: 8000, Gateway: 15888, Dashboard: 8501
   - **Data Initialization:**
     - How init.sql runs on first startup
     - How to manually trigger data ingestion: `python scripts/ingest_data.py --symbol X:BTCUSD --timeframe 1m --days 365`
   - **Exchange Credential Setup:**
     - Binance: API key + secret, how to create on Binance
     - Gateway DEX setup: reference to `docker/gateway/gateway-setup-instructions.md`
   - **Troubleshooting:**
     - Common issues: DB connection refused, API auth failure, Gateway passphrase mismatch
     - How to check logs: `docker compose logs <service>`
     - How to reset: `docker compose down -v && docker compose up -d`

2. Create `docs/mcp-workflows.md`:
   - **Overview:** What MCP is, how it connects AI agents to Hummingbot
   - **Setup:** How to configure `.mcp.json` for Claude Code or other MCP clients
   - **Workflow Examples** (each with natural language command and what happens step-by-step):
     - **"Deploy SniperProX on BTC-USDT perpetuals on Binance with 28-bar length, Jurik MA":**
       1. MCP agent reads request
       2. Creates/loads YAML config with specified params
       3. Calls `BotDeployer.deploy_bot()` which POSTs to Hummingbot API
       4. Hummingbot creates V2 script instance with SniperController
       5. Controller starts receiving candles and computing signals
       6. PositionExecutor opens/closes positions based on signals
       7. Dashboard shows live bot status
     - **"Check my portfolio":**
       1. MCP calls `list_bots()` via Hummingbot API
       2. For each bot, fetches P&L from `bot_performance` table
       3. Returns summary: bot name, P&L, win rate, active positions
     - **"Stop the Sniper BTC bot":**
       1. MCP calls `stop_bot("sniper_btcusdt_binance_1h")`
       2. Hummingbot gracefully stops the bot
       3. Confirms bot is stopped
     - **"What are the dominant cycles on ETH right now?":**
       1. MCP queries `dominant_cycles` table
       2. Returns dominant period per timeframe with power scores
     - **"Backtest VZO on SOL-USDT for the last 30 days":**
       1. MCP fetches 30 days of SOL-USDT 1h data from TimescaleDB
       2. Runs VZOProX indicator
       3. Runs VBT `Portfolio.from_signals()` backtest
       4. Returns: total return, Sharpe ratio, max drawdown, win rate
     - **"Deploy all configs in the examples directory":**
       1. MCP calls `deploy_all("src/config/examples/")`
       2. Each YAML config is loaded and deployed sequentially
       3. Returns status per bot
   - **Available MCP Tools:**
     - Table listing Hummingbot MCP tools with descriptions
   - **Custom Workflows:**
     - How to extend MCP workflows by adding new Python scripts
     - How to create custom YAML configs for new strategies

3. Create `docs/indicators.md`:
   - **Universal MA Library (34 types):**
     - Table listing all 34 MA types with: name, abbreviation, key parameters, description
     - Usage example: `UniversalMA.run(close, length=20, ma_type="Jurik Moving Average")`
     - Performance note: all @njit accelerated
   - **SniperProX:**
     - Description: Triple stochastic crossover + Fisher transform + ADX/DMI filter
     - Parameters table: name, type, default, range, description
       - `length: int = 28` (1-200)
       - `ma_type: str = "Jurik Moving Average"` (any of 34 types)
       - `overbought_oversold: float = 1.386` (0.5-3.0)
       - `trail_threshold: float = 0.986` (0.9-1.0)
       - `dmi_len: int = 14` (5-50)
       - `adx_threshold: float = 20.0` (10-50)
     - Signal logic: entry when Fisher cross + ADX above threshold + DMI directional
     - Usage example with VBT IndicatorFactory
   - **VZOProX:**
     - Description: Volume Zone Oscillator with trend confirmation
     - Parameters table: name, type, default, range, description
       - `length: int = 14` (5-100)
       - `ma_type: str = "Exponential Moving Average"` (any of 34 types)
       - `coeff: float = 0.2` (0.01-1.0)
       - `overbought: float = 40.0` (20-80)
       - `oversold: float = -40.0` (-80 to -20)
     - Signal logic: cross above oversold = long, cross below overbought = short
     - Usage example
   - **SpectralAnalysis:**
     - Description: Dominant cycle detection using Hurst bandpass and Goertzel DFT
     - Parameters table:
       - `method: str = "goertzel"` ("hurst" or "goertzel")
       - `min_period: int = 10` (2-500)
       - `max_period: int = 200` (10-5000)
       - `num_periods: int = 50` (10-500)
     - Output: dominant_period, power, composite_waveform
     - Usage example
   - **AstroLib & CelestialChannels:**
     - Brief description of astronomical calculation modules
     - Note: advanced feature, planetary cycle calculations
     - Parameters and usage
   - **Signal Combiner:**
     - Description: Merges multiple indicator signals into one decision
     - Modes: AND (all agree), OR (any triggers), WEIGHTED (weighted vote)
     - Configuration example
     - Usage example

4. Create `docs/architecture.md`:
   - **System Overview:**
     - Copy Mermaid diagram from PRD-001 (the full system diagram)
     - Add brief description of each layer
   - **Data Flow Diagram:**
     ```mermaid
     sequenceDiagram
         participant P as Polygon.io
         participant U as DataUpdater
         participant T as TimescaleDB
         participant I as VBT Indicators
         participant S as Signal Combiner
         participant C as V2 Controller
         participant H as Hummingbot API
         participant E as Exchange

         U->>P: Pull OHLCV data
         P-->>U: Return candles
         U->>T: Write to ohlcv table
         C->>T: Read candles
         C->>I: Compute indicators
         I-->>C: Return signals
         C->>S: Combine signals
         S-->>C: Final signal
         C->>H: Signal (1/-1/0)
         H->>E: Execute trade
     ```
   - **Component Architecture:**
     - For each major component (Data, Indicators, Controllers, Dashboard, Config):
       - Purpose, key files, dependencies, interfaces
   - **Database Schema:**
     - ER diagram (Mermaid) showing all 4 tables and their relationships
     - Table descriptions with column details
   - **Docker Service Map:**
     - Mermaid diagram showing Docker services, networks, volumes, ports
   - **Technology Stack:**
     - Table from PRD (Technology Decisions) with additional implementation notes

5. Create `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "hummingbot": {
         "command": "docker",
         "args": ["exec", "-i", "uptrade-hummingbot-mcp-1", "python", "-m", "hummingbot_mcp"],
         "env": {
           "HB_API_URL": "http://hummingbot-api:8000",
           "HB_API_USER": "${HB_API_USER}",
           "HB_API_PASSWORD": "${HB_API_PASSWORD}"
         }
       }
     }
   }
   ```
   - Configure Hummingbot MCP server connection
   - Uses Docker exec to connect to the running MCP container
   - Environment variables reference the `.env` file

6. Update `README.md`:
   - **Project title and tagline:** "UpTrade — AI-Powered Crypto Trading Platform"
   - **One-paragraph description:** VBT Pro indicators + Hummingbot execution + TimescaleDB + MCP orchestration
   - **Key Features list:**
     - 34 MA types + SniperProX, VZOProX, SpectralAnalysis indicators
     - Hummingbot V2 directional trading controllers
     - CEX + DEX support (Binance, Uniswap, Jupiter, Hyperliquid, dYdX)
     - Multi-timeframe dominant cycle detection
     - Streamlit dashboard with real-time monitoring
     - MCP integration for AI agent orchestration
     - Docker Compose one-command deployment
   - **Quick Start (3 steps):**
     1. Clone, configure `.env`, `docker compose up`
     2. Deploy a bot: `python scripts/deploy_bot.py deploy src/config/examples/sniper_btcusdt_binance.yml`
     3. Open dashboard: `http://localhost:8501`
   - **Architecture diagram** (Mermaid, simplified version)
   - **Links to detailed docs:**
     - [Deployment Guide](docs/deployment.md)
     - [MCP Workflows](docs/mcp-workflows.md)
     - [Indicator Reference](docs/indicators.md)
     - [Architecture](docs/architecture.md)
   - **Project Structure** — directory tree showing key files
   - **License / Credits** — VBT Pro, Hummingbot, Polygon.io

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify all files exist
test -f docs/deployment.md && echo "OK: deployment" || echo "FAIL: deployment"
test -f docs/mcp-workflows.md && echo "OK: mcp-workflows" || echo "FAIL: mcp-workflows"
test -f docs/indicators.md && echo "OK: indicators" || echo "FAIL: indicators"
test -f docs/architecture.md && echo "OK: architecture" || echo "FAIL: architecture"
test -f .mcp.json && echo "OK: mcp.json" || echo "FAIL: mcp.json"
test -f README.md && echo "OK: README" || echo "FAIL: README"

# Verify .mcp.json is valid JSON
python3 -c "import json; json.load(open('.mcp.json')); print('.mcp.json is valid JSON')"

# Verify .mcp.json has required structure
python3 -c "
import json
config = json.load(open('.mcp.json'))
assert 'mcpServers' in config, 'Missing mcpServers'
assert 'hummingbot' in config['mcpServers'], 'Missing hummingbot server'
hb = config['mcpServers']['hummingbot']
assert 'command' in hb, 'Missing command'
print('.mcp.json structure OK')
"

# Verify docs have required content
python3 -c "
# Deployment doc
d = open('docs/deployment.md').read()
for kw in ['docker compose', '.env', 'TimescaleDB', 'API key', 'Troubleshooting']:
    assert kw.lower() in d.lower(), f'deployment.md missing: {kw}'
print('deployment.md content OK')
"

python3 -c "
# MCP workflows doc
d = open('docs/mcp-workflows.md').read()
for kw in ['Deploy SniperProX', 'portfolio', 'backtest', 'dominant cycle']:
    assert kw.lower() in d.lower(), f'mcp-workflows.md missing: {kw}'
print('mcp-workflows.md content OK')
"

python3 -c "
# Indicators doc
d = open('docs/indicators.md').read()
for kw in ['SniperProX', 'VZOProX', 'SpectralAnalysis', 'Universal MA', 'Signal Combiner', 'Jurik']:
    assert kw in d, f'indicators.md missing: {kw}'
print('indicators.md content OK')
"

python3 -c "
# Architecture doc
d = open('docs/architecture.md').read()
assert 'mermaid' in d.lower(), 'architecture.md missing Mermaid diagrams'
for kw in ['TimescaleDB', 'Hummingbot', 'Controller', 'Dashboard']:
    assert kw in d, f'architecture.md missing: {kw}'
print('architecture.md content OK')
"

python3 -c "
# README
d = open('README.md').read()
for kw in ['UpTrade', 'docker compose', 'deploy', 'dashboard']:
    assert kw.lower() in d.lower(), f'README.md missing: {kw}'
print('README.md content OK')
"

# Verify docs word counts (should be substantial)
wc -w docs/*.md README.md
```

### Success Criteria
- [ ] `docs/deployment.md` covers prerequisites, quick start, env vars, service ports, troubleshooting
- [ ] `docs/mcp-workflows.md` has at least 6 workflow examples with step-by-step explanations
- [ ] `docs/indicators.md` documents all indicators with parameters, defaults, ranges, and usage examples
- [ ] `docs/architecture.md` includes at least 3 Mermaid diagrams (system, data flow, Docker services)
- [ ] `.mcp.json` is valid JSON with Hummingbot MCP server configuration
- [ ] `README.md` has overview, quickstart, architecture diagram, and links to all docs
- [ ] All docs reference correct file paths within the project
- [ ] Indicator parameter tables include type, default, range, and description for every parameter
- [ ] MCP workflows explain the full chain from natural language command to trade execution
- [ ] Deployment guide works for both Docker and local development setups
