# PRP-011: Gateway DEX Setup

**Wave:** 3 (Execution)
**Dependencies:** PRP-001 (Docker stack)
**Branch:** `feature/prp-011-gateway-dex`
**Estimated Effort:** 2.5 hours
**PRD Reference:** PRD-001, Epic 4 (US-4.3), Epic 3 (US-3.3)

---

## Context Layer

### Goal
Configure Hummingbot Gateway for DEX trading across multiple chains and protocols. Gateway provides a standardized REST API that abstracts DEX interactions (swaps, liquidity, order placement) behind a unified interface. This PRP sets up Gateway in Docker Compose, creates configuration helpers, and documents how to add wallet keys for each supported chain.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- Hummingbot Gateway (hummingbot/gateway:latest Docker image)
- Supported DEX protocols:
  - Uniswap V3 (Ethereum mainnet, Polygon, Arbitrum)
  - Jupiter (Solana)
  - Hyperliquid DEX (perpetuals)
  - dYdX v4 (Cosmos-based perpetuals)
- Gateway REST API (port 15888)
- Python httpx for Gateway API calls
- YAML/JSON for Gateway chain and connector configuration

### Files to Create
1. `docker/gateway/` — Directory for Gateway configuration files
2. `docker/gateway/gateway-setup-instructions.md` — Step-by-step wallet setup documentation
3. `src/config/gateway_config.py` — Gateway connector configuration and health check utilities
4. `scripts/setup_gateway.py` — Script to configure Gateway connectors interactively

### Architecture Decisions
- **Gateway runs as a Docker service** defined in PRP-001's `docker-compose.yml`. This PRP adds Gateway-specific configuration, volume mounts for certs/configs, and environment variables.
- **Gateway passphrase** is stored in `.env` as `GW_PASSPHRASE`. All wallet keys are encrypted with this passphrase inside the Gateway container.
- **Chain configuration:** Gateway uses chain-specific config files. We provide templates for Ethereum, Polygon, Arbitrum, Solana, and Cosmos (for dYdX).
- **Connector setup flow:** `setup_gateway.py` calls Gateway API endpoints to:
  1. Check Gateway health
  2. Add chain configs (RPC endpoints)
  3. Add wallet keys (encrypted with passphrase)
  4. Verify connector status
- **No private keys in code or config files.** All keys are added via Gateway API at runtime and stored encrypted inside the Gateway container volume.
- **Network topology:** Gateway communicates with Hummingbot API over the internal `uptrade-net` Docker network. Only port 15888 is exposed for local management.
- **RPC endpoints:** Users must provide their own RPC endpoints (Infura, Alchemy, Helius, etc.) via `.env` variables.

### Gateway API Reference
```
# Health check
GET /gateway/status -> {"status": "ok", "version": "..."}

# List available connectors
GET /gateway/connectors -> {"connectors": [...]}

# Add wallet
POST /gateway/wallet/add
{
  "chain": "ethereum",
  "network": "mainnet",
  "privateKey": "0x...",
  "address": "0x..."
}

# Check balances
POST /gateway/wallet/balances
{
  "chain": "ethereum",
  "network": "mainnet",
  "address": "0x...",
  "tokenSymbols": ["ETH", "USDC"]
}

# Approve token spending (needed for DEX swaps)
POST /gateway/evm/approve
{
  "chain": "ethereum",
  "network": "mainnet",
  "address": "0x...",
  "spender": "uniswap",
  "token": "USDC"
}
```

---

## Task Layer

### Tasks

1. Create `docker/gateway/` directory and `docker/gateway/gateway-setup-instructions.md`:
   - Document Gateway overview and what it does
   - Document supported chains and connectors:
     - **Ethereum mainnet:** Uniswap V3 — needs ETH RPC (Infura/Alchemy), EVM wallet private key
     - **Polygon:** Uniswap V3 — needs Polygon RPC, EVM wallet private key (same key works)
     - **Arbitrum:** Uniswap V3 — needs Arbitrum RPC, EVM wallet private key
     - **Solana:** Jupiter — needs Solana RPC (Helius/QuickNode), Solana wallet private key (base58)
     - **Hyperliquid:** — needs Hyperliquid API key and secret (generated from Hyperliquid UI)
     - **dYdX v4:** — needs dYdX mnemonic phrase, Cosmos RPC
   - Step-by-step for each chain:
     1. Add RPC endpoint to `.env`
     2. Run `python scripts/setup_gateway.py add-wallet --chain <chain>`
     3. Verify with `python scripts/setup_gateway.py check --chain <chain>`
   - Security warnings: never commit private keys, use hardware wallets for mainnet, test on testnets first

2. Update `.env.example` references (document these variables, do NOT modify PRP-001's file directly):
   ```
   # Gateway
   GW_PASSPHRASE=your_gateway_passphrase
   GW_API_URL=http://localhost:15888

   # RPC Endpoints
   ETH_RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY
   POLYGON_RPC_URL=https://polygon-mainnet.infura.io/v3/YOUR_KEY
   ARBITRUM_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
   SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
   HYPERLIQUID_API_KEY=
   HYPERLIQUID_API_SECRET=
   DYDX_MNEMONIC=
   ```

3. Create `src/config/gateway_config.py`:
   - `class GatewayConfig(BaseModel)`:
     - `api_url: str` — default from env `GW_API_URL` or `http://localhost:15888`
     - `passphrase: str` — from env `GW_PASSPHRASE`
   - `class ChainConfig(BaseModel)`:
     - `chain: str` — "ethereum", "polygon", "arbitrum", "solana", "hyperliquid", "dydx"
     - `network: str` — "mainnet", "testnet"
     - `rpc_url: str`
     - `connector: str` — "uniswap", "jupiter", "hyperliquid", "dydx"
   - `SUPPORTED_CHAINS: dict[str, ChainConfig]` — predefined configs for each supported chain/connector
   - `class GatewayClient`:
     - `__init__(self, config: GatewayConfig = None)` — load from Settings if not provided
     - `async health_check(self) -> dict` — GET `/gateway/status`
     - `async list_connectors(self) -> list[str]` — GET `/gateway/connectors`
     - `async add_wallet(self, chain: str, network: str, private_key: str, address: str = None) -> dict` — POST `/gateway/wallet/add`
     - `async get_balances(self, chain: str, network: str, address: str, tokens: list[str]) -> dict` — POST `/gateway/wallet/balances`
     - `async approve_token(self, chain: str, network: str, address: str, spender: str, token: str) -> dict` — POST `/gateway/evm/approve`
     - `async check_connector_status(self, chain: str) -> dict` — verify chain is connected and wallet is configured
     - Implement async context manager

4. Create `scripts/setup_gateway.py`:
   - Argparse CLI with subcommands:
     - `health` — check Gateway is running and responsive
     - `connectors` — list available connectors
     - `add-wallet --chain <chain> --network <network>` — interactively prompt for private key (using `getpass`) and add wallet via Gateway API
     - `check --chain <chain>` — verify connector is configured and wallet has balance
     - `approve --chain <chain> --token <token> --spender <connector>` — approve token spending for DEX
     - `balances --chain <chain> --address <address> --tokens <token1,token2>` — check wallet balances
   - Uses `GatewayClient` from `src/config/gateway_config.py`
   - All subcommands are async, wrapped with `asyncio.run()`
   - Private key input uses `getpass.getpass()` to avoid terminal echo
   - Print results as formatted output (not raw JSON, human-readable)
   - Usage examples:
     ```
     python scripts/setup_gateway.py health
     python scripts/setup_gateway.py add-wallet --chain ethereum --network mainnet
     python scripts/setup_gateway.py check --chain ethereum
     python scripts/setup_gateway.py approve --chain ethereum --token USDC --spender uniswap
     python scripts/setup_gateway.py balances --chain ethereum --address 0x... --tokens ETH,USDC
     ```

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify files exist
test -d docker/gateway && echo "OK: gateway dir" || echo "FAIL: gateway dir"
test -f docker/gateway/gateway-setup-instructions.md && echo "OK: docs" || echo "FAIL: docs"
test -f src/config/gateway_config.py && echo "OK: config" || echo "FAIL: config"
test -f scripts/setup_gateway.py && echo "OK: setup script" || echo "FAIL: setup script"

# Verify imports
python3 -c "from src.config.gateway_config import GatewayConfig, GatewayClient, ChainConfig, SUPPORTED_CHAINS; print(f'Supported chains: {list(SUPPORTED_CHAINS.keys())}')"

# Verify chain configs
python3 -c "
from src.config.gateway_config import SUPPORTED_CHAINS
required = ['ethereum', 'polygon', 'arbitrum', 'solana', 'hyperliquid', 'dydx']
for chain in required:
    assert chain in SUPPORTED_CHAINS, f'Missing chain: {chain}'
    print(f'{chain}: connector={SUPPORTED_CHAINS[chain].connector}')
print('All chains configured')
"

# Verify GatewayClient instantiation
python3 -c "
from src.config.gateway_config import GatewayClient, GatewayConfig
client = GatewayClient(GatewayConfig(api_url='http://localhost:15888', passphrase='test'))
print('GatewayClient created OK')
"

# Verify CLI help
python3 scripts/setup_gateway.py --help
python3 scripts/setup_gateway.py health --help

# Verify documentation exists and covers all chains
python3 -c "
content = open('docker/gateway/gateway-setup-instructions.md').read()
for chain in ['Ethereum', 'Polygon', 'Arbitrum', 'Solana', 'Jupiter', 'Hyperliquid', 'dYdX']:
    assert chain in content, f'Missing docs for {chain}'
print('All chains documented')
"
```

### Success Criteria
- [ ] `docker/gateway/` directory exists with setup instructions
- [ ] Documentation covers all 6 chains/connectors with step-by-step wallet setup
- [ ] `GatewayClient` has methods: `health_check`, `list_connectors`, `add_wallet`, `get_balances`, `approve_token`, `check_connector_status`
- [ ] `SUPPORTED_CHAINS` includes ethereum, polygon, arbitrum, solana, hyperliquid, dydx
- [ ] `setup_gateway.py` CLI has subcommands: health, connectors, add-wallet, check, approve, balances
- [ ] Private key input uses `getpass` (no terminal echo)
- [ ] Gateway health endpoint check works (`GET /gateway/status`)
- [ ] Security: no private keys stored in code or config files
- [ ] All env variables documented for RPC endpoints
