# Hummingbot Gateway DEX Setup

## Overview

Hummingbot Gateway is a middleware service that provides a standardised REST API for
interacting with decentralised exchanges (DEXs) and blockchain networks. UpTrade uses
the Gateway to execute on-chain trades, manage wallets, and approve token spending.

The Gateway runs as a standalone Docker container (or process) and exposes its API on
port **15888** by default. UpTrade communicates with it through the `GatewayClient`
class in `src/config/gateway_config.py`.

### Architecture

```
UpTrade  ──HTTP──►  Gateway (localhost:15888)  ──RPC──►  Blockchain Node
                         │
                         ├── Uniswap V3 connector (Ethereum, Polygon, Arbitrum)
                         ├── Jupiter connector (Solana)
                         ├── Hyperliquid connector
                         └── dYdX v4 connector
```

---

## Supported Chains

| Chain | Network | DEX / Connector | Native Token |
|-------|---------|-----------------|--------------|
| Ethereum | mainnet | Uniswap V3 | ETH |
| Polygon | mainnet | Uniswap V3 | MATIC |
| Arbitrum | mainnet | Uniswap V3 | ETH |
| Solana | mainnet | Jupiter | SOL |
| Hyperliquid | mainnet | Hyperliquid | USDC |
| dYdX | mainnet | dYdX v4 | USDC |

---

## Prerequisites

- Docker and Docker Compose installed
- An RPC endpoint for each chain you wish to trade on (Alchemy, Infura, QuickNode, etc.)
- A funded wallet for each chain
- The Gateway passphrase (set during first start)

---

## General Setup

1. **Pull the Gateway image**
   ```bash
   docker pull hummingbot/gateway:latest
   ```

2. **Set environment variables** in your `.env` file:
   ```bash
   GW_PASSPHRASE=<your-gateway-passphrase>
   GW_API_URL=http://localhost:15888
   ```

3. **Start the Gateway**
   ```bash
   docker run -d --name gateway \
     -p 15888:15888 \
     -e GATEWAY_PASSPHRASE=$GW_PASSPHRASE \
     hummingbot/gateway:latest
   ```

4. **Verify health**
   ```bash
   python scripts/setup_gateway.py health
   ```

---

## Chain-Specific Setup

### Ethereum (Uniswap V3)

**Required environment variables:**
```bash
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/<YOUR_KEY>
ETH_PRIVATE_KEY=<your-ethereum-private-key>   # Never commit this!
ETH_WALLET_ADDRESS=0x...
```

**Steps:**
1. Obtain an Ethereum mainnet RPC URL from Alchemy, Infura, or a similar provider.
2. Fund your wallet with ETH for gas and the tokens you wish to trade.
3. Add the wallet to the Gateway:
   ```bash
   python scripts/setup_gateway.py add-wallet --chain ethereum --network mainnet
   ```
   You will be prompted for the private key (input is hidden).
4. Approve tokens for the Uniswap connector:
   ```bash
   python scripts/setup_gateway.py approve --chain ethereum --token USDC --spender uniswap
   ```
5. Verify the connector:
   ```bash
   python scripts/setup_gateway.py check --chain ethereum
   ```

### Polygon (Uniswap V3)

**Required environment variables:**
```bash
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/<YOUR_KEY>
POLYGON_PRIVATE_KEY=<your-polygon-private-key>
POLYGON_WALLET_ADDRESS=0x...
```

**Steps:**
1. Obtain a Polygon mainnet RPC URL.
2. Fund your wallet with MATIC for gas.
3. Add the wallet:
   ```bash
   python scripts/setup_gateway.py add-wallet --chain polygon --network mainnet
   ```
4. Approve tokens:
   ```bash
   python scripts/setup_gateway.py approve --chain polygon --token USDC --spender uniswap
   ```
5. Verify:
   ```bash
   python scripts/setup_gateway.py check --chain polygon
   ```

### Arbitrum (Uniswap V3)

**Required environment variables:**
```bash
ARBITRUM_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/<YOUR_KEY>
ARBITRUM_PRIVATE_KEY=<your-arbitrum-private-key>
ARBITRUM_WALLET_ADDRESS=0x...
```

**Steps:**
1. Obtain an Arbitrum mainnet RPC URL.
2. Fund your wallet with ETH on Arbitrum for gas.
3. Add the wallet:
   ```bash
   python scripts/setup_gateway.py add-wallet --chain arbitrum --network mainnet
   ```
4. Approve tokens:
   ```bash
   python scripts/setup_gateway.py approve --chain arbitrum --token USDC --spender uniswap
   ```
5. Verify:
   ```bash
   python scripts/setup_gateway.py check --chain arbitrum
   ```

### Solana (Jupiter)

**Required environment variables:**
```bash
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY=<your-solana-private-key>
SOLANA_WALLET_ADDRESS=<base58-address>
```

**Steps:**
1. Obtain a Solana mainnet RPC URL (Helius, QuickNode, or the public endpoint).
2. Fund your wallet with SOL for transaction fees.
3. Add the wallet:
   ```bash
   python scripts/setup_gateway.py add-wallet --chain solana --network mainnet
   ```
4. Jupiter does not require separate token approvals on Solana.
5. Verify:
   ```bash
   python scripts/setup_gateway.py check --chain solana
   ```

### Hyperliquid

**Required environment variables:**
```bash
HYPERLIQUID_PRIVATE_KEY=<your-hyperliquid-private-key>
HYPERLIQUID_WALLET_ADDRESS=0x...
```

**Steps:**
1. Hyperliquid uses its own L1; no external RPC URL is needed.
2. Fund your account with USDC via the Hyperliquid bridge.
3. Add the wallet:
   ```bash
   python scripts/setup_gateway.py add-wallet --chain hyperliquid --network mainnet
   ```
4. Verify:
   ```bash
   python scripts/setup_gateway.py check --chain hyperliquid
   ```

### dYdX v4

**Required environment variables:**
```bash
DYDX_MNEMONIC=<your-dydx-mnemonic>
DYDX_WALLET_ADDRESS=dydx1...
```

**Steps:**
1. dYdX v4 runs on its own Cosmos-based chain; no external RPC URL is needed.
2. Fund your dYdX account with USDC.
3. Add the wallet:
   ```bash
   python scripts/setup_gateway.py add-wallet --chain dydx --network mainnet
   ```
4. Verify:
   ```bash
   python scripts/setup_gateway.py check --chain dydx
   ```

---

## Security Warnings

> **NEVER** commit private keys, mnemonics, or passphrases to version control.

- Store all secrets in `.env` files that are listed in `.gitignore`.
- Use a hardware wallet or a secrets manager in production.
- The `add-wallet` CLI command uses `getpass` to avoid echoing the private key.
- Rotate keys immediately if you suspect they have been exposed.
- Limit RPC endpoint access with IP allowlists when possible.

---

## Troubleshooting

### Gateway not reachable
- Confirm the container is running: `docker ps | grep gateway`
- Check logs: `docker logs gateway`
- Ensure port 15888 is not blocked by a firewall.
- Verify `GW_API_URL` matches the running Gateway address.

### Connector not available
- Run `python scripts/setup_gateway.py connectors` to list installed connectors.
- Restart the Gateway after configuration changes.
- Some connectors require chain-specific configuration files inside the container.

### Token approval fails
- Ensure the wallet has enough native token for gas (ETH, MATIC, etc.).
- Verify the token symbol is correct and supported on the chain.
- Check the Gateway logs for detailed error messages.

### Wallet add fails
- Double-check the private key format (hex for EVM chains, base58 for Solana).
- Ensure the chain and network names match exactly (e.g., `ethereum`, `mainnet`).
- The Gateway must be running before you can add wallets.

### RPC errors
- Verify the RPC URL is correct and the provider plan has sufficient capacity.
- Try a different RPC provider if you receive rate-limit errors.
- For Solana, the public RPC endpoint has strict rate limits; consider a paid provider.
