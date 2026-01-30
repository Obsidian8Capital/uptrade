# PRP-009: Hummingbot V2 Controller Bridge

**Wave:** 3 (Execution)
**Dependencies:** PRP-006 (indicators), PRP-008 (signal combiner)
**Branch:** `feature/prp-009-v2-controller-bridge`
**Estimated Effort:** 4 hours
**PRD Reference:** PRD-001, Epic 3 (US-3.1, US-3.2, US-3.3)

---

## Context Layer

### Goal
Create Hummingbot V2 DirectionalTrading controllers that consume VBT Pro indicator signals. Each controller subclasses Hummingbot's `DirectionalTradingControllerBase`, overrides `update_processed_data()` to run VBT indicators on incoming candles, and returns signal dictionaries (`{"signal": 1/-1/0}`) that Hummingbot's PositionExecutor uses to open/close directional trades. Three concrete controllers are needed: SniperProX, VZOProX, and SpectralAnalysis (adaptive cycle-based).

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- Hummingbot V2 Controller framework (`hummingbot.strategy_v2.controllers`)
- `DirectionalTradingControllerBase` and `DirectionalTradingControllerConfigBase`
- VBT Pro IndicatorFactory outputs (from `src/indicators/`)
- Signal Combiner (from `src/signals/combiner.py`)
- Pydantic v2 for config validation
- pandas DataFrames for candle data
- numpy for signal arrays

### Files to Create
1. `src/controllers/__init__.py` — Package init, exports all controllers
2. `src/controllers/base_vbt_controller.py` — Base class extending DirectionalTradingControllerBase
3. `src/controllers/sniper_controller.py` — SniperProX directional controller
4. `src/controllers/vzo_controller.py` — VZOProX directional controller
5. `src/controllers/cycle_controller.py` — SpectralAnalysis adaptive cycle controller

### Architecture Decisions
- **Base controller pattern:** `BaseVBTController` handles the common flow: fetch candles from Hummingbot connectors -> convert to pandas DataFrame -> call abstract `compute_indicators(df)` -> extract signal -> return Hummingbot signal format. Subclasses only implement `compute_indicators()`.
- **Config classes** extend `DirectionalTradingControllerConfigBase` with indicator-specific parameters (e.g., `length`, `ma_type`, `overbought_oversold` for Sniper).
- **Signal format:** Controllers return `{"signal": 1}` (long), `{"signal": -1}` (short), or `{"signal": 0}` (neutral) — the format Hummingbot PositionExecutor expects.
- **Indicator imports:** Controllers import from `src/indicators/` (SniperProX, VZOProX, SpectralAnalysis) which are VBT IndicatorFactory wrappers around Numba kernels.
- **No direct exchange calls:** Controllers receive candle data from Hummingbot's connector framework; they only compute signals.
- **Adaptive cycle controller:** The cycle controller queries the `dominant_cycles` TimescaleDB table (via `src/data/`) to dynamically adjust indicator lengths based on the current dominant cycle period.
- **Controller naming convention:** `controller_type = "vbt_sniper"`, `controller_type = "vbt_vzo"`, `controller_type = "vbt_cycle"` — prefixed with `vbt_` to distinguish from native Hummingbot controllers.

### Hummingbot V2 Controller Interface Reference
```python
# Hummingbot expects controllers to follow this pattern:
class DirectionalTradingControllerBase:
    def __init__(self, config, market_data_provider, actions_proposal_timeout=None):
        ...
    async def update_processed_data(self):
        """Called on each candle. Must populate self.processed_data with signal info."""
        ...
    def get_signal(self) -> int:
        """Returns 1 (long), -1 (short), or 0 (neutral)."""
        ...

class DirectionalTradingControllerConfigBase(BaseModel):
    controller_type: str
    connector_name: str
    trading_pair: str
    total_amount_quote: Decimal
    max_executors_per_side: int
    cooldown_time: int
    leverage: int
    stop_loss: Decimal
    take_profit: Decimal
    time_limit: int
    # Subclasses add indicator-specific params
```

---

## Task Layer

### Tasks

1. Create `src/controllers/__init__.py`:
   - Export `BaseVBTController`, `BaseVBTControllerConfig`
   - Export `SniperController`, `SniperControllerConfig`
   - Export `VZOController`, `VZOControllerConfig`
   - Export `CycleController`, `CycleControllerConfig`
   - Provide `CONTROLLER_REGISTRY` dict mapping controller_type strings to classes

2. Create `src/controllers/base_vbt_controller.py`:
   - `BaseVBTControllerConfig(DirectionalTradingControllerConfigBase)`:
     - `controller_type: str`
     - `candles_max: int = 300` — max candles to use for indicator computation
     - `timeframe: str = "1h"`
   - `BaseVBTController(DirectionalTradingControllerBase)`:
     - `__init__(self, config: BaseVBTControllerConfig, market_data_provider, actions_proposal_timeout=None)`
     - Store config, initialize `self._current_signal = 0`
     - `async update_processed_data(self)`:
       1. Get candles from `self.market_data_provider.get_candles(connector=config.connector_name, trading_pair=config.trading_pair, interval=config.timeframe, max_records=config.candles_max)`
       2. Convert to pandas DataFrame with columns: `[timestamp, open, high, low, close, volume]`
       3. Call `self.compute_signal(df)` (abstract method)
       4. Store result in `self._current_signal`
       5. Set `self.processed_data["signal"] = self._current_signal`
     - Abstract method: `compute_signal(self, df: pd.DataFrame) -> int` — subclasses implement this
     - `get_signal(self) -> int` — returns `self._current_signal`
     - Helper: `_candles_to_dataframe(self, candles) -> pd.DataFrame` — converts Hummingbot candle format to pandas

3. Create `src/controllers/sniper_controller.py`:
   - `SniperControllerConfig(BaseVBTControllerConfig)`:
     - `controller_type: str = "vbt_sniper"`
     - `length: int = 28`
     - `ma_type: str = "Jurik Moving Average"`
     - `overbought_oversold: float = 1.386`
     - `trail_threshold: float = 0.986`
     - `dmi_len: int = 14`
     - `adx_threshold: float = 20.0`
   - `SniperController(BaseVBTController)`:
     - `compute_signal(self, df: pd.DataFrame) -> int`:
       1. Import SniperProX from `src.indicators.sniper`
       2. Run SniperProX on df with config params
       3. Extract latest signal: `entries[-1]` = 1 (long), `exits[-1]` = -1 (short), else 0
       4. Return signal integer

4. Create `src/controllers/vzo_controller.py`:
   - `VZOControllerConfig(BaseVBTControllerConfig)`:
     - `controller_type: str = "vbt_vzo"`
     - `length: int = 14`
     - `ma_type: str = "Exponential Moving Average"`
     - `coeff: float = 0.2`
     - `overbought: float = 40.0`
     - `oversold: float = -40.0`
   - `VZOController(BaseVBTController)`:
     - `compute_signal(self, df: pd.DataFrame) -> int`:
       1. Import VZOProX from `src.indicators.vzo`
       2. Run VZOProX on df with config params
       3. Extract latest signal from VZO output (above overbought = -1 short reversal, below oversold = 1 long reversal, cross of zero line = directional signal)
       4. Return signal integer

5. Create `src/controllers/cycle_controller.py`:
   - `CycleControllerConfig(BaseVBTControllerConfig)`:
     - `controller_type: str = "vbt_cycle"`
     - `method: str = "goertzel"` — "hurst" or "goertzel"
     - `min_period: int = 10`
     - `max_period: int = 200`
     - `base_ma_type: str = "Exponential Moving Average"`
     - `adaptive: bool = True` — use dominant cycle as indicator length
     - `timeframes: list[str] = ["5m", "1h", "4h", "1d"]`
   - `CycleController(BaseVBTController)`:
     - `compute_signal(self, df: pd.DataFrame) -> int`:
       1. Import SpectralAnalysis from `src.indicators.spectral`
       2. If `adaptive=True`, query `dominant_cycles` table for current dominant period (fallback to `min_period` if no data)
       3. Run SpectralAnalysis with dynamic length = dominant cycle period
       4. Extract composite cycle value: positive = upward cycle = 1 (long), negative = downward cycle = -1 (short), near zero = 0 (neutral)
       5. Return signal integer
     - Helper: `_get_dominant_period(self, symbol: str, timeframe: str) -> int` — queries TimescaleDB for latest dominant cycle period

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify all files exist
test -f src/controllers/__init__.py && echo "OK: __init__" || echo "FAIL: __init__"
test -f src/controllers/base_vbt_controller.py && echo "OK: base" || echo "FAIL: base"
test -f src/controllers/sniper_controller.py && echo "OK: sniper" || echo "FAIL: sniper"
test -f src/controllers/vzo_controller.py && echo "OK: vzo" || echo "FAIL: vzo"
test -f src/controllers/cycle_controller.py && echo "OK: cycle" || echo "FAIL: cycle"

# Verify imports work
python3 -c "from src.controllers import SniperController, SniperControllerConfig; print('Sniper OK')"
python3 -c "from src.controllers import VZOController, VZOControllerConfig; print('VZO OK')"
python3 -c "from src.controllers import CycleController, CycleControllerConfig; print('Cycle OK')"
python3 -c "from src.controllers import CONTROLLER_REGISTRY; print(f'Registry has {len(CONTROLLER_REGISTRY)} controllers')"

# Verify config models validate
python3 -c "
from src.controllers.sniper_controller import SniperControllerConfig
c = SniperControllerConfig(connector_name='binance_perpetual', trading_pair='BTC-USDT', total_amount_quote=500, max_executors_per_side=2, cooldown_time=300, leverage=10, stop_loss=0.03, take_profit=0.02, time_limit=2700)
print(f'Sniper config: {c.controller_type}, length={c.length}, ma={c.ma_type}')
"

# Verify base class has abstract method
python3 -c "
from src.controllers.base_vbt_controller import BaseVBTController
try:
    # Should not be instantiable directly
    import inspect
    assert 'compute_signal' in dir(BaseVBTController)
    print('Base class has compute_signal method')
except Exception as e:
    print(f'ERROR: {e}')
"
```

### Success Criteria
- [ ] All 5 files exist in `src/controllers/`
- [ ] `BaseVBTController` defines abstract `compute_signal(df) -> int`
- [ ] `BaseVBTController.update_processed_data()` handles candle fetch -> indicator -> signal flow
- [ ] `SniperController` computes signal from SniperProX indicator with configurable params
- [ ] `VZOController` computes signal from VZOProX indicator with configurable params
- [ ] `CycleController` computes signal from SpectralAnalysis with optional adaptive cycle length
- [ ] All config classes extend `DirectionalTradingControllerConfigBase` with proper defaults
- [ ] `CONTROLLER_REGISTRY` maps `"vbt_sniper"`, `"vbt_vzo"`, `"vbt_cycle"` to their classes
- [ ] Signal output is always `1`, `-1`, or `0` (integer)
- [ ] No direct exchange API calls in any controller (signals only)
