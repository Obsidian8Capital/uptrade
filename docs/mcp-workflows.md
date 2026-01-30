# MCP Workflow Guide

## Overview

UpTrade integrates with the **Hummingbot MCP server** to enable AI-agent-driven trading operations. An MCP-compatible AI assistant (Claude, etc.) can deploy bots, check portfolio status, run backtests, and analyze market cycles through natural language.

The MCP server runs as a Docker container (`uptrade-hb-mcp`) and communicates via **stdio transport** with the AI agent. It proxies commands to the Hummingbot REST API (`uptrade-hb-api`) and the UpTrade indicator/data layer.

```
AI Agent (Claude) <--stdio--> MCP Server <--HTTP--> Hummingbot API
                                                   |
                                              TimescaleDB
                                                   |
                                              Polygon.io
```

---

## Setup

### 1. Configure `.mcp.json`

The `.mcp.json` file in the project root tells the AI agent how to connect to the MCP server:

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

### 2. Start Docker Services

```bash
cd docker
docker compose up -d
```

### 3. Verify MCP Container

```bash
docker ps | grep mcp
# Should show: uptrade-hb-mcp running
```

---

## Workflow Examples

### 1. Deploy SniperProX on BTC-USDT

**User prompt:** "Deploy SniperProX on BTC-USDT with 10x leverage on Binance"

**Steps the AI agent performs:**

1. Load or create a bot deployment config:
   ```yaml
   bot_name: sniper_btcusdt_binance_1h
   indicator:
     name: SniperProX
     params:
       length: 28
       ma_type: "Jurik Moving Average"
       overbought_oversold: 1.386
       trail_threshold: 0.986
       dmi_len: 14
       adx_thresh: 20
   market:
     exchange: binance_perpetual
     pair: BTC-USDT
     timeframe: 1h
     candles_max: 300
   execution:
     leverage: 10
     stop_loss: 0.03
     take_profit: 0.02
     time_limit: 2700
     max_executors: 2
     cooldown: 300
     amount_quote: 500
     position_mode: HEDGE
   data:
     source: polygon
     symbol_override: "X:BTCUSD"
   ```

2. Call the Hummingbot API deploy endpoint:
   ```
   POST /bot-orchestration/deploy-v2-script
   ```

3. Confirm deployment status.

**Example MCP tool call:**
```
deploy_bot(config_path="src/config/examples/sniper_btcusdt_binance.yml")
```

---

### 2. Check Portfolio

**User prompt:** "Check my portfolio"

**Steps:**

1. List all active bots:
   ```
   GET /bot-orchestration/status
   ```

2. For each bot, retrieve performance metrics from the `bot_performance` table.

3. Summarize positions, P&L, win rates, and drawdowns.

**Example MCP tool call:**
```
list_bots()
```

---

### 3. Stop a Bot

**User prompt:** "Stop the Sniper BTC bot"

**Steps:**

1. Resolve bot name: `sniper_btcusdt_binance_1h`
2. Call stop endpoint:
   ```
   POST /bot-orchestration/stop-bot
   {"bot_name": "sniper_btcusdt_binance_1h"}
   ```
3. Confirm the bot has stopped.

**Example MCP tool call:**
```
stop_bot(bot_name="sniper_btcusdt_binance_1h")
```

---

### 4. Analyze Dominant Cycles

**User prompt:** "What are the dominant cycles on ETH?"

**Steps:**

1. Pull multi-timeframe OHLCV data for ETH from TimescaleDB (5m, 1h, 4h, 1d).
2. Run `MTFCycleDetector` with Goertzel spectral analysis.
3. Return per-timeframe dominant cycle periods and composite score.

**Example output:**
```json
{
  "symbol": "X:ETHUSD",
  "timeframes": {
    "5m":  {"dominant_cycle_name": "5d",  "dominant_period": 4.3,  "dominant_power": 0.0234},
    "1h":  {"dominant_cycle_name": "20d", "dominant_period": 17.0, "dominant_power": 0.0891},
    "4h":  {"dominant_cycle_name": "40d", "dominant_period": 34.1, "dominant_power": 0.1205},
    "1d":  {"dominant_cycle_name": "20w", "dominant_period": 136.4,"dominant_power": 0.0567}
  },
  "composite_score": 47.3,
  "suggested_length": 47
}
```

---

### 5. Backtest VZO on SOL-USDT

**User prompt:** "Backtest VZO on SOL-USDT for 30 days"

**Steps:**

1. Pull 30 days of SOL-USDT OHLCV data from TimescaleDB.
2. Run `VZOProX` indicator to generate entry/exit signals.
3. Execute `vbt.Portfolio.from_signals()` backtest.
4. Return stats: total return, Sharpe ratio, max drawdown, number of trades.

**Example output:**
```
Total Return:    +8.42%
Sharpe Ratio:    1.87
Max Drawdown:    -3.21%
Total Trades:    24
Win Rate:        62.5%
```

**Example MCP tool call:**
```
run_backtest(symbol="SOL-USDT", indicator="VZOProX", days=30)
```

---

### 6. Deploy All Configs

**User prompt:** "Deploy all configs"

**Steps:**

1. Scan `src/config/examples/` for all `.yml` files.
2. Validate each config with `BotDeploymentConfig`.
3. Deploy each bot sequentially via the Hummingbot API.
4. Report success/failure for each.

**Example MCP tool call:**
```
deploy_all(directory="src/config/examples/")
```

**CLI equivalent:**
```bash
python scripts/deploy_bot.py deploy-all src/config/examples/
```

---

## Available MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `deploy_bot` | Deploy a bot from a YAML config | `config_path` |
| `deploy_all` | Deploy all bots in a directory | `directory` |
| `stop_bot` | Stop a running bot | `bot_name` |
| `list_bots` | List all active bots and statuses | — |
| `get_bot_status` | Get status of a specific bot | `bot_name` |
| `run_backtest` | Backtest an indicator on a symbol | `symbol`, `indicator`, `days`, `params` |
| `detect_cycles` | Run multi-timeframe cycle analysis | `symbol`, `timeframes`, `method` |
| `optimize_params` | Grid-search indicator parameters | `indicator`, `symbol`, `param_ranges` |
| `ingest_data` | Pull and store historical data | `symbol`, `timeframe`, `start`, `end` |

---

## Custom Workflows

You can chain multiple MCP tools into a workflow. Example multi-step workflow:

**"Optimize and deploy the best SniperProX config for ETH"**

1. **Detect cycles** on ETH to find the optimal lookback length.
2. **Optimize** SniperProX parameters using the suggested length as a starting point.
3. **Backtest** the top parameter set to confirm performance.
4. **Deploy** the bot with optimized parameters.

Each step feeds its output into the next, allowing the AI agent to make data-driven deployment decisions.
