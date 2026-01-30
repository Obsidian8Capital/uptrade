# PRP-010: Bot Config & Deployment System

**Wave:** 3 (Execution)
**Dependencies:** PRP-002 (bot config), PRP-009 (controllers)
**Branch:** `feature/prp-010-bot-deployment`
**Estimated Effort:** 3 hours
**PRD Reference:** PRD-001, Epic 4 (US-4.1, US-4.2)

---

## Context Layer

### Goal
Create the bot deployment system that takes a `BotDeploymentConfig` (YAML-defined in PRP-002) and deploys it as a live Hummingbot V2 script via the Hummingbot API. This includes deploying, stopping, listing bots, and a CLI entry point for command-line bot management.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- Hummingbot API REST endpoints (running on port 8000 in Docker)
- httpx for async HTTP client (preferred over requests for async support)
- Pydantic models from PRP-002 (`BotDeploymentConfig`, `load_bot_config`)
- V2 Controllers from PRP-009 (controller_type registry)
- Python argparse for CLI
- Basic Auth for Hummingbot API authentication

### Files to Create
1. `src/config/deployer.py` — `BotDeployer` class with deploy/stop/list methods
2. `scripts/deploy_bot.py` — CLI entry point for bot deployment

### Architecture Decisions
- **Hummingbot API endpoints used:**
  - `POST /bot-orchestration/deploy-v2-script` — deploy a V2 strategy with controller config
  - `POST /bot-orchestration/stop-bot` — stop a running bot by name
  - `GET /bot-orchestration/status` — list all active bots and their status
  - `GET /bot-orchestration/bot-status/{bot_name}` — get specific bot status
- **Authentication:** Basic Auth with `HB_API_USER` and `HB_API_PASSWORD` from `.env` (loaded via `src/config/settings.py`)
- **API base URL:** `http://localhost:8000` (configurable via `HB_API_URL` env var)
- **Deploy payload format:** The deployer translates `BotDeploymentConfig` into the JSON payload format expected by Hummingbot's V2 script deployment endpoint, mapping indicator config to controller config params.
- **Error handling:** Raise `DeploymentError` with status code and response body on API failure. Retry once on connection error.
- **Async-first:** All deployer methods are async (using httpx.AsyncClient). Sync wrappers provided for CLI usage via `asyncio.run()`.
- **YAML-to-deploy flow:** `load_bot_config(yaml_path)` -> `BotDeploymentConfig` -> `deployer.deploy_bot(config)` -> Hummingbot API call -> returns bot instance info.

### Hummingbot API Deploy Payload Reference
```json
{
  "controller_config": {
    "controller_type": "vbt_sniper",
    "connector_name": "binance_perpetual",
    "trading_pair": "BTC-USDT",
    "total_amount_quote": 500,
    "max_executors_per_side": 2,
    "cooldown_time": 300,
    "leverage": 10,
    "stop_loss": 0.03,
    "take_profit": 0.02,
    "time_limit": 2700,
    "length": 28,
    "ma_type": "Jurik Moving Average",
    "overbought_oversold": 1.386,
    "trail_threshold": 0.986,
    "dmi_len": 14,
    "adx_threshold": 20.0,
    "candles_max": 300,
    "timeframe": "1h"
  },
  "bot_name": "sniper_btcusdt_binance_1h"
}
```

---

## Task Layer

### Tasks

1. Create `src/config/deployer.py`:
   - `class DeploymentError(Exception)`:
     - `status_code: int`
     - `detail: str`
     - `response_body: dict | None`
   - `class BotDeployer`:
     - `__init__(self, api_url: str = None, username: str = None, password: str = None)`:
       - Load defaults from `Settings` if not provided
       - Store auth credentials
       - Create httpx.AsyncClient with base_url and Basic Auth
     - `async deploy_bot(self, config: BotDeploymentConfig) -> dict`:
       1. Convert `BotDeploymentConfig` to Hummingbot API payload:
          - Map `config.indicator.params` + `config.market` + `config.execution` into flat `controller_config` dict
          - Set `controller_type` based on `config.indicator.name` -> controller type mapping (SniperProX -> "vbt_sniper", VZOProX -> "vbt_vzo", SpectralAnalysis -> "vbt_cycle")
          - Set `bot_name` from `config.bot_name`
       2. POST to `/bot-orchestration/deploy-v2-script`
       3. Return response JSON on success (201/200)
       4. Raise `DeploymentError` on failure
     - `async stop_bot(self, bot_name: str) -> dict`:
       1. POST to `/bot-orchestration/stop-bot` with `{"bot_name": bot_name}`
       2. Return response JSON
     - `async list_bots(self) -> list[dict]`:
       1. GET `/bot-orchestration/status`
       2. Return list of bot status dicts
     - `async get_bot_status(self, bot_name: str) -> dict`:
       1. GET `/bot-orchestration/bot-status/{bot_name}`
       2. Return bot status dict
     - `async deploy_from_yaml(self, path: str) -> dict`:
       1. Call `load_bot_config(path)` from PRP-002
       2. Call `self.deploy_bot(config)`
       3. Return result
     - `async deploy_all(self, directory: str) -> list[dict]`:
       1. Glob all `.yml`/`.yaml` files in directory
       2. Load each with `load_bot_config()`
       3. Deploy each sequentially (to avoid overwhelming the API)
       4. Return list of results (success or error per config)
     - `async close(self)` — close httpx client
     - Implement async context manager (`__aenter__`, `__aexit__`)
   - Helper function: `_indicator_to_controller_type(indicator_name: str) -> str`:
     - Maps: "SniperProX" -> "vbt_sniper", "VZOProX" -> "vbt_vzo", "SpectralAnalysis" -> "vbt_cycle"
     - Raises `ValueError` for unknown indicators

2. Create `scripts/deploy_bot.py`:
   - Argparse CLI with subcommands:
     - `deploy <yaml_path>` — deploy a single bot from YAML config
     - `deploy-all <directory>` — deploy all configs in a directory
     - `stop <bot_name>` — stop a running bot
     - `list` — list all active bots
     - `status <bot_name>` — get specific bot status
   - Each subcommand calls the appropriate `BotDeployer` async method via `asyncio.run()`
   - Print results as formatted JSON
   - Exit code 0 on success, 1 on failure
   - Usage examples in `--help`:
     ```
     python scripts/deploy_bot.py deploy src/config/examples/sniper_btcusdt_binance.yml
     python scripts/deploy_bot.py deploy-all src/config/examples/
     python scripts/deploy_bot.py stop sniper_btcusdt_binance_1h
     python scripts/deploy_bot.py list
     python scripts/deploy_bot.py status sniper_btcusdt_binance_1h
     ```
   - Add shebang `#!/usr/bin/env python3`

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify files exist
test -f src/config/deployer.py && echo "OK: deployer" || echo "FAIL: deployer"
test -f scripts/deploy_bot.py && echo "OK: CLI" || echo "FAIL: CLI"

# Verify imports
python3 -c "from src.config.deployer import BotDeployer, DeploymentError; print('BotDeployer OK')"

# Verify deployer instantiation (without live API)
python3 -c "
from src.config.deployer import BotDeployer
d = BotDeployer(api_url='http://localhost:8000', username='admin', password='admin')
print(f'Deployer created, base_url={d._client.base_url if hasattr(d, \"_client\") else \"OK\"} ')
"

# Verify config-to-payload mapping
python3 -c "
from src.config.deployer import _indicator_to_controller_type
assert _indicator_to_controller_type('SniperProX') == 'vbt_sniper'
assert _indicator_to_controller_type('VZOProX') == 'vbt_vzo'
assert _indicator_to_controller_type('SpectralAnalysis') == 'vbt_cycle'
print('Controller type mapping OK')
"

# Verify CLI help works
python3 scripts/deploy_bot.py --help
python3 scripts/deploy_bot.py deploy --help
```

### Success Criteria
- [ ] `BotDeployer` class has methods: `deploy_bot`, `stop_bot`, `list_bots`, `get_bot_status`, `deploy_from_yaml`, `deploy_all`
- [ ] `deploy_bot()` correctly translates `BotDeploymentConfig` to Hummingbot API payload format
- [ ] `_indicator_to_controller_type()` maps all 3 indicator names to controller types
- [ ] `DeploymentError` includes status_code and detail
- [ ] `BotDeployer` supports async context manager pattern
- [ ] CLI script has 5 subcommands: deploy, deploy-all, stop, list, status
- [ ] CLI prints formatted JSON output
- [ ] CLI exits with code 0 on success, 1 on failure
- [ ] Authentication uses Basic Auth from env vars
- [ ] Error handling retries once on connection error
