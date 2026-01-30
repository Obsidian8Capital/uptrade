# PRP-008: Signal Combiner V2

**Wave:** 2 (Indicators)
**Dependencies:** PRP-006 (needs ported indicator code in `src/indicators/`)
**Branch:** `feature/prp-008-signal-combiner`
**Estimated Effort:** 3 hours
**PRD Reference:** PRD-001, Epic 2 (US-2.3)

---

## Context Layer

### Goal
Create an enhanced signal combiner that merges multiple indicator outputs into a single actionable signal array (1, 0, -1) compatible with Hummingbot V2 Controllers. Support four combination modes: AND (all agree), OR (any triggers), WEIGHTED (weighted vote), and CONFIRM (primary + secondary confirmation). The combiner must be configurable via YAML as part of the BotDeploymentConfig.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- NumPy for array operations
- pandas for Series handling
- YAML configuration (integrates with PRP-002's `BotDeploymentConfig`)
- `src/indicators/` (PRP-006) for indicator signal formats

### Files to Create
1. `src/signals/__init__.py` — Signals package init
2. `src/signals/combiner.py` — Enhanced signal combiner

### Existing Signals Module (from `/home/ai-coder/Projects/vectorbt.pro/Pinescript/vbt/signals.py`)
The existing `generate_signals()` function only supports AND/OR with SniperProX + VZO. The new combiner generalizes this to:
- Support arbitrary indicators (not just Sniper + VZO)
- Add WEIGHTED and CONFIRM modes
- Output int signals (1, 0, -1) instead of boolean entries/exits
- Accept config from YAML

### Hummingbot V2 Controller Signal Format
Hummingbot V2 DirectionalTradingController expects:
- `signal_value`: integer where 1 = long, -1 = short, 0 = neutral
- The controller checks `signal_value` on each candle to decide whether to create executors

### Indicator Signal Format (from PRP-006 indicators)
Each VBT indicator produces signal arrays where:
- `major_buy` / `minor_buy` — NaN where no signal, non-NaN where signal fires
- Converting to int: `signal = np.where(~np.isnan(major_buy), 1, np.where(~np.isnan(major_sell), -1, 0))`

### YAML Configuration Example (extends PRP-002's BotDeploymentConfig)
```yaml
bot_name: sniper_vzo_btcusdt_binance
signals:
  mode: weighted  # and | or | weighted | confirm
  indicators:
    - name: SniperProX
      weight: 0.6
      role: primary          # for confirm mode
      signal_source: major   # "major" = major_buy/major_sell, "minor" = minor signals
    - name: VZOProX
      weight: 0.3
      role: secondary        # for confirm mode
      signal_source: major
    - name: SpectralAnalysis
      weight: 0.1
      role: secondary
      signal_source: composite  # use composite > 0 for long, < 0 for short
  weighted_threshold: 0.5    # minimum weighted score to trigger signal
  confirm_window: 3          # bars within which secondary must confirm primary
```

### Architecture Decisions
- **Input format**: dict of `{indicator_name: np.ndarray}` where each array contains integer signals (1, 0, -1)
- **Output format**: single `np.ndarray` of integers (1, 0, -1) — same length as input arrays
- **AND mode**: all indicators must agree on direction (all 1 = long, all -1 = short, otherwise 0)
- **OR mode**: any indicator signaling triggers (first non-zero wins, or majority direction if conflicting)
- **WEIGHTED mode**: each indicator's signal multiplied by its weight, sum compared to threshold
- **CONFIRM mode**: primary indicator must signal first, then at least one secondary must confirm within N bars
- **Configurable via Pydantic models** that integrate with PRP-002's BotDeploymentConfig
- **Stateless per-bar** for AND/OR/WEIGHTED; CONFIRM mode maintains a rolling window state

---

## Task Layer

### Tasks

1. Create `src/signals/__init__.py`:
   ```python
   """Signal combination and processing for UpTrade."""
   from src.signals.combiner import SignalCombiner, CombineMode  # noqa: F401
   ```

2. Create `src/signals/combiner.py` with the following components:

   2a. **Enum** `CombineMode`:
   ```python
   from enum import Enum

   class CombineMode(str, Enum):
       AND = "and"
       OR = "or"
       WEIGHTED = "weighted"
       CONFIRM = "confirm"
   ```

   2b. **Pydantic model** `IndicatorSignalConfig`:
   ```python
   from pydantic import BaseModel, Field
   from typing import Optional

   class IndicatorSignalConfig(BaseModel):
       name: str                              # Indicator name (e.g., "SniperProX")
       weight: float = 1.0                    # Weight for WEIGHTED mode
       role: str = "secondary"                # "primary" or "secondary" for CONFIRM mode
       signal_source: str = "major"           # "major", "minor", or "composite"
   ```

   2c. **Pydantic model** `SignalCombinerConfig`:
   ```python
   class SignalCombinerConfig(BaseModel):
       mode: CombineMode = CombineMode.AND
       indicators: list[IndicatorSignalConfig] = Field(default_factory=list)
       weighted_threshold: float = 0.5        # Min score for WEIGHTED mode
       confirm_window: int = 3                # Bars for CONFIRM mode lookahead
   ```

   2d. **Class** `SignalCombiner`:

   **Constructor** `__init__(self, config: SignalCombinerConfig = None, mode: str = "and")`:
   - Accept either a `SignalCombinerConfig` object or a simple `mode` string
   - If `config` is None, create a default config with the given mode
   - Store config
   - Initialize logger

   **Method** `combine(self, signals: dict[str, np.ndarray]) -> np.ndarray`:
   - Main entry point — dispatch to the appropriate mode method
   - Validate all input arrays have the same length
   - `signals` is a dict like `{"SniperProX": array([1, 0, -1, 0, ...]), "VZOProX": array([0, 0, -1, 0, ...])}`
   - Dispatch based on `self.config.mode`:
     - AND → `_combine_and(signals)`
     - OR → `_combine_or(signals)`
     - WEIGHTED → `_combine_weighted(signals)`
     - CONFIRM → `_combine_confirm(signals)`
   - Return int array of shape `(n_bars,)` with values in {-1, 0, 1}

   **Method** `_combine_and(self, signals: dict[str, np.ndarray]) -> np.ndarray`:
   - Stack all signal arrays into a 2D matrix: `(n_indicators, n_bars)`
   - For each bar:
     - If ALL indicators == 1: output 1 (long)
     - If ALL indicators == -1: output -1 (short)
     - Otherwise: output 0 (neutral)
   - Vectorized: `all_long = np.all(matrix == 1, axis=0)`, `all_short = np.all(matrix == -1, axis=0)`
   - `result = np.where(all_long, 1, np.where(all_short, -1, 0))`

   **Method** `_combine_or(self, signals: dict[str, np.ndarray]) -> np.ndarray`:
   - For each bar:
     - If ANY indicator == 1 AND no indicator == -1: output 1
     - If ANY indicator == -1 AND no indicator == 1: output -1
     - If conflicting (some 1, some -1): use majority vote (count 1s vs -1s)
     - If all neutral: output 0
   - Vectorized with `np.sum()` and `np.sign()`

   **Method** `_combine_weighted(self, signals: dict[str, np.ndarray]) -> np.ndarray`:
   - Get weights from config: `weights[indicator_name] = config.indicators[i].weight`
   - For each bar:
     - Compute weighted sum: `score = sum(signal[bar] * weight for signal, weight in zip(...))`
     - Normalize by total weight: `score /= sum(weights)`
     - If `score >= threshold`: output 1
     - If `score <= -threshold`: output -1
     - Else: output 0
   - Vectorized: build weight vector, matrix multiply, threshold

   **Method** `_combine_confirm(self, signals: dict[str, np.ndarray]) -> np.ndarray`:
   - Identify primary indicator(s) from config (role == "primary")
   - Identify secondary indicator(s) from config (role == "secondary")
   - For each bar where primary signals (non-zero):
     - Look ahead `confirm_window` bars in secondary signals
     - If any secondary confirms (same direction) within the window: output primary's direction
     - Else: output 0
   - Implementation: iterate bars (not easily vectorizable due to lookahead)
   - Edge case: if no primary defined, fall back to AND mode

   **Static method** `convert_indicator_output(indicator_result, signal_source: str = "major") -> np.ndarray`:
   - Convert VBT IndicatorFactory output to integer signal array
   - If `signal_source == "major"`:
     - `buy = ~np.isnan(np.asarray(indicator_result.major_buy, dtype=np.float64))`
     - `sell = ~np.isnan(np.asarray(indicator_result.major_sell, dtype=np.float64))`
     - `signal = np.where(buy, 1, np.where(sell, -1, 0))`
   - If `signal_source == "minor"`:
     - Same but with `minor_buy` / `minor_sell`
   - If `signal_source == "composite"`:
     - `composite = np.asarray(indicator_result.composite, dtype=np.float64)`
     - `signal = np.where(composite > 0, 1, np.where(composite < 0, -1, 0))`
   - Return int array

   **Class method** `from_yaml(cls, config_dict: dict) -> SignalCombiner`:
   - Parse a YAML-style dict (the `signals:` section of a BotDeploymentConfig)
   - Create `SignalCombinerConfig` from it
   - Return `SignalCombiner(config=config)`

   **Method** `to_dict(self) -> dict`:
   - Serialize config back to dict (for YAML export)
   - Return `self.config.model_dump()`

3. Update PRP-002's `BotDeploymentConfig` — add optional `signals` field:
   - NOTE: If PRP-002 is not yet implemented, document the expected integration:
   ```python
   # In src/config/bot_config.py (PRP-002), add:
   from src.signals.combiner import SignalCombinerConfig

   class BotDeploymentConfig(BaseModel):
       # ... existing fields ...
       signals: Optional[SignalCombinerConfig] = None
   ```
   - If PRP-002 is already done, create a note in the code that this integration should be done.

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify imports
python3 -c "
from src.signals import SignalCombiner, CombineMode
from src.signals.combiner import SignalCombinerConfig, IndicatorSignalConfig
print('All imports OK')
print('CombineMode values:', [m.value for m in CombineMode])
"

# Verify class methods
python3 -c "
import inspect
from src.signals.combiner import SignalCombiner
methods = ['combine', '_combine_and', '_combine_or', '_combine_weighted', '_combine_confirm', 'convert_indicator_output', 'from_yaml', 'to_dict']
for m in methods:
    assert hasattr(SignalCombiner, m), f'Missing method: {m}'
print('All methods present')
"

# Test AND mode
python3 -c "
import numpy as np
from src.signals.combiner import SignalCombiner

combiner = SignalCombiner(mode='and')
signals = {
    'A': np.array([1, 1, -1, 0, 1]),
    'B': np.array([1, 0, -1, 0, 1]),
}
result = combiner.combine(signals)
expected = np.array([1, 0, -1, 0, 1])
assert np.array_equal(result, expected), f'AND failed: {result} != {expected}'
print('AND mode OK:', result)
"

# Test OR mode
python3 -c "
import numpy as np
from src.signals.combiner import SignalCombiner

combiner = SignalCombiner(mode='or')
signals = {
    'A': np.array([1, 0, 0, -1, 0]),
    'B': np.array([0, 0, -1, 0, 0]),
}
result = combiner.combine(signals)
# A=1,B=0 -> 1; A=0,B=0 -> 0; A=0,B=-1 -> -1; A=-1,B=0 -> -1; 0,0 -> 0
expected = np.array([1, 0, -1, -1, 0])
assert np.array_equal(result, expected), f'OR failed: {result} != {expected}'
print('OR mode OK:', result)
"

# Test WEIGHTED mode
python3 -c "
import numpy as np
from src.signals.combiner import SignalCombiner, SignalCombinerConfig, IndicatorSignalConfig, CombineMode

config = SignalCombinerConfig(
    mode=CombineMode.WEIGHTED,
    indicators=[
        IndicatorSignalConfig(name='A', weight=0.7),
        IndicatorSignalConfig(name='B', weight=0.3),
    ],
    weighted_threshold=0.5,
)
combiner = SignalCombiner(config=config)
signals = {
    'A': np.array([1, 1, -1, 0]),
    'B': np.array([0, 1, 1, 0]),
}
result = combiner.combine(signals)
# bar0: 0.7*1 + 0.3*0 = 0.7 >= 0.5 -> 1
# bar1: 0.7*1 + 0.3*1 = 1.0 >= 0.5 -> 1
# bar2: 0.7*-1 + 0.3*1 = -0.4, abs < 0.5 -> 0
# bar3: 0 -> 0
expected = np.array([1, 1, 0, 0])
assert np.array_equal(result, expected), f'WEIGHTED failed: {result} != {expected}'
print('WEIGHTED mode OK:', result)
"

# Test output is always int array with values in {-1, 0, 1}
python3 -c "
import numpy as np
from src.signals.combiner import SignalCombiner

for mode in ['and', 'or']:
    combiner = SignalCombiner(mode=mode)
    signals = {'A': np.array([1, 0, -1, 1, -1]), 'B': np.array([-1, 0, -1, 1, 0])}
    result = combiner.combine(signals)
    assert result.dtype in [np.int32, np.int64, np.intp, int], f'Must be int, got {result.dtype}'
    assert set(np.unique(result)).issubset({-1, 0, 1}), f'Values must be in {{-1, 0, 1}}, got {np.unique(result)}'
    print(f'{mode} output OK: dtype={result.dtype}, values={np.unique(result)}')
print('Output format OK')
"

# Test from_yaml
python3 -c "
from src.signals.combiner import SignalCombiner
config_dict = {
    'mode': 'weighted',
    'indicators': [
        {'name': 'SniperProX', 'weight': 0.6, 'role': 'primary'},
        {'name': 'VZOProX', 'weight': 0.4, 'role': 'secondary'},
    ],
    'weighted_threshold': 0.5,
}
combiner = SignalCombiner.from_yaml(config_dict)
assert combiner.config.mode.value == 'weighted'
assert len(combiner.config.indicators) == 2
print('from_yaml OK')
"

# Verify Pydantic validation
python3 -c "
from src.signals.combiner import SignalCombinerConfig, CombineMode
config = SignalCombinerConfig(mode='and')
assert config.mode == CombineMode.AND
print('Pydantic validation OK')
d = config.model_dump()
print('model_dump OK:', d)
"
```

### Success Criteria
- [ ] `src/signals/__init__.py` exists and exports `SignalCombiner`, `CombineMode`
- [ ] `src/signals/combiner.py` exists with `SignalCombiner`, `SignalCombinerConfig`, `IndicatorSignalConfig`, `CombineMode`
- [ ] `CombineMode` enum has values: `and`, `or`, `weighted`, `confirm`
- [ ] `SignalCombiner.combine()` dispatches to the correct mode method
- [ ] AND mode: all indicators must agree for non-zero output
- [ ] OR mode: any non-zero indicator triggers, majority vote on conflicts
- [ ] WEIGHTED mode: weighted sum compared to configurable threshold
- [ ] CONFIRM mode: primary must signal, secondary must confirm within window
- [ ] Output is always `np.ndarray` of integers with values in {-1, 0, 1}
- [ ] `convert_indicator_output()` converts VBT IndicatorFactory output to int signals
- [ ] `from_yaml()` creates combiner from dict (YAML config section)
- [ ] `to_dict()` serializes config back to dict
- [ ] `SignalCombinerConfig` is a Pydantic BaseModel with validation
- [ ] All 4 mode tests pass with expected outputs
- [ ] Combiner works with arbitrary number of indicators (not hardcoded to Sniper + VZO)
