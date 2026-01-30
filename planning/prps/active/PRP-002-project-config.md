# PRP-002: Project Configuration & Package Structure

**Wave:** 0 (Foundation)
**Dependencies:** None (parallel with PRP-001)
**Branch:** `feature/prp-002-project-config`
**Estimated Effort:** 1.5 hours
**PRD Reference:** PRD-001, Epic 6 (US-6.2)

---

## Context Layer

### Goal
Set up the Python package structure, shared types, enums, logging configuration, and the bot deployment configuration system (YAML-based) that all subsequent PRPs depend on.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Files to Create
1. `src/__init__.py` — Package root with version
2. `src/types.py` — Shared type definitions (BotConfig, IndicatorConfig, ExchangeConfig, TimeframeEnum)
3. `src/enums.py` — Indicator type enum, exchange type enum, signal direction enum
4. `src/logging_config.py` — Structured logging setup (JSON format for Docker)
5. `src/config/__init__.py` — Config package
6. `src/config/bot_config.py` — Pydantic models for bot deployment YAML configs
7. `src/config/examples/` — Example YAML configs for different bot deployments
8. `src/config/examples/sniper_btcusdt_binance.yml` — Example: SniperProX on BTC-USDT Binance perps
9. `src/config/examples/vzo_ethusdc_uniswap.yml` — Example: VZO on ETH-USDC Uniswap spot DEX
10. `src/config/examples/cycle_solusdt_hyperliquid.yml` — Example: Spectral cycle on SOL-USDT Hyperliquid

### Architecture Decisions

**Bot Config YAML Structure:**
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
market:
  exchange: binance_perpetual
  pair: BTC-USDT
  timeframe: 1h
  candles_max: 300
execution:
  strategy: directional_trading
  leverage: 10
  stop_loss: 0.03
  take_profit: 0.02
  time_limit: 2700
  max_executors: 2
  cooldown: 300
  amount_quote: 500
  position_mode: HEDGE
data:
  source: polygon  # or "exchange" for direct exchange candles
  symbol_override: "X:BTCUSD"  # Polygon symbol format
```

**Pydantic models** validate all configs at load time. Invalid configs fail fast with clear error messages.

---

## Task Layer

### Tasks

1. Create `src/__init__.py` with version `__version__ = "0.1.0"`

2. Create `src/enums.py`:
   - `IndicatorType` enum: SNIPER, VZO, SPECTRAL, UNIVERSAL_MA, CELESTIAL, CUSTOM
   - `ExchangeType` enum: CEX, DEX
   - `SignalDirection` enum: LONG=1, NEUTRAL=0, SHORT=-1
   - `TimeframeEnum`: M1, M5, M15, M30, H1, H4, D1, W1

3. Create `src/types.py`:
   - Type aliases for common VBT/pandas types
   - `OHLCVData` TypedDict
   - `SignalResult` NamedTuple (signal, value, timestamp)

4. Create `src/config/bot_config.py`:
   - `IndicatorConfig(BaseModel)` — name, params dict
   - `MarketConfig(BaseModel)` — exchange, pair, timeframe, candles_max
   - `ExecutionConfig(BaseModel)` — strategy, leverage, stop_loss, take_profit, etc.
   - `DataConfig(BaseModel)` — source, symbol_override
   - `BotDeploymentConfig(BaseModel)` — bot_name, indicator, market, execution, data
   - `load_bot_config(path: str) -> BotDeploymentConfig` — YAML loader with validation
   - `load_all_configs(directory: str) -> List[BotDeploymentConfig]` — bulk loader

5. Create `src/logging_config.py`:
   - JSON structured logging formatter
   - `setup_logging(level="INFO")` function
   - Logger factory: `get_logger(name: str)`

6. Create 3 example YAML configs demonstrating different deployment scenarios

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade
python3 -c "from src.enums import IndicatorType, SignalDirection; print(IndicatorType.SNIPER, SignalDirection.LONG)"
python3 -c "from src.config.bot_config import BotDeploymentConfig, load_bot_config; c = load_bot_config('src/config/examples/sniper_btcusdt_binance.yml'); print(c.bot_name)"
python3 -c "from src.logging_config import setup_logging, get_logger; setup_logging(); log = get_logger('test'); log.info('OK')"
```

### Success Criteria
- [ ] All enums importable and have correct values
- [ ] BotDeploymentConfig validates example YAML configs
- [ ] Invalid config raises clear Pydantic ValidationError
- [ ] Logger outputs JSON-formatted log lines
- [ ] 3 example configs cover CEX perps, DEX spot, and adaptive cycle scenarios
