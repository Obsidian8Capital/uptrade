# PRP-006: Port Indicator Engine

**Wave:** 2 (Indicators)
**Dependencies:** PRP-001 (project structure only — no DB or data pipeline needed)
**Branch:** `feature/prp-006-port-indicators`
**Estimated Effort:** 4 hours
**PRD Reference:** PRD-001, Epic 2 (US-2.1)

---

## Context Layer

### Goal
Copy and adapt all custom indicator code from `/home/ai-coder/Projects/vectorbt.pro/Pinescript/vbt/` into the UpTrade project at `src/indicators/`. Update all import paths from `Pinescript.vbt.*` to `src.indicators.*` and add clean `__init__.py` exports so all indicators are usable via `from src.indicators import SniperProX, VZOProX, SpectralAnalysis, UniversalMA`.

### Working Directory
`/home/ai-coder/Projects/uptrade`

### Technology
- VectorBT Pro (`vectorbtpro.indicators.factory.IndicatorFactory`)
- Numba (`@njit` compiled kernels)
- NumPy, pandas

### Source Files (copy FROM)
All files are in `/home/ai-coder/Projects/vectorbt.pro/Pinescript/vbt/`:

**Numba kernels** (in `nb/` subdirectory):
1. `nb/__init__.py` — Kernel package init
2. `nb/ma_library_nb.py` — 34 MA types as @njit functions + universal dispatcher (~900 lines)
3. `nb/vzo_nb.py` — VZO core kernel (~140 lines)
4. `nb/sniper_nb.py` — SniperProX kernel: triple stochastic, Fisher, ADX/DMI (~200 lines)
5. `nb/spectral_nb.py` — Hurst bandpass + Goertzel DFT (~100 lines)
6. `nb/astro_nb.py` — Astronomical calculations: Kepler, ephemeris (~300 lines)

**IndicatorFactory wrappers**:
7. `ma_library.py` — UniversalMA IndicatorFactory (~100 lines)
8. `vzo.py` — VZOProX IndicatorFactory (~100 lines)
9. `sniper.py` — SniperProX IndicatorFactory (~100 lines)
10. `spectral.py` — SpectralAnalysis IndicatorFactory (~80 lines)
11. `astro_lib.py` — Python convenience layer for astro calcs (~120 lines)
12. `celestial_channels.py` — Planetary channel levels (~80 lines)

**Signal/backtest/optimize**:
13. `signals.py` — Signal combiner: generate_signals() (~80 lines)
14. `backtest.py` — VBT Portfolio.from_signals() pipeline (~50 lines)
15. `optimize.py` — Grid search optimizer (~120 lines)

### Files to Create
1. `src/indicators/__init__.py` — Package init with clean exports
2. `src/indicators/nb/__init__.py` — Numba kernel package init
3. `src/indicators/nb/ma_library_nb.py` — Copied + import paths updated
4. `src/indicators/nb/vzo_nb.py` — Copied + import paths updated
5. `src/indicators/nb/sniper_nb.py` — Copied + import paths updated
6. `src/indicators/nb/spectral_nb.py` — Copied + import paths updated
7. `src/indicators/nb/astro_nb.py` — Copied + import paths updated
8. `src/indicators/ma_library.py` — Copied + import paths updated
9. `src/indicators/vzo.py` — Copied + import paths updated
10. `src/indicators/sniper.py` — Copied + import paths updated
11. `src/indicators/spectral.py` — Copied + import paths updated
12. `src/indicators/astro_lib.py` — Copied + import paths updated
13. `src/indicators/celestial_channels.py` — Copied + import paths updated
14. `src/indicators/signals.py` — Copied + import paths updated
15. `src/indicators/backtest.py` — Copied + import paths updated
16. `src/indicators/optimize.py` — Copied + import paths updated

### Architecture Decisions
- **Copy, don't symlink** — UpTrade must be a standalone project without dependency on the vectorbt.pro repo
- **Preserve all existing logic exactly** — no functional changes to indicator math, only import path updates
- **Import path mapping**:
  - `from Pinescript.vbt.nb.ma_library_nb import ...` → `from src.indicators.nb.ma_library_nb import ...`
  - `from Pinescript.vbt.nb.sniper_nb import ...` → `from src.indicators.nb.sniper_nb import ...`
  - `from Pinescript.vbt.nb.vzo_nb import ...` → `from src.indicators.nb.vzo_nb import ...`
  - `from Pinescript.vbt.nb.spectral_nb import ...` → `from src.indicators.nb.spectral_nb import ...`
  - `from Pinescript.vbt.sniper import SniperProX` → `from src.indicators.sniper import SniperProX`
  - `from Pinescript.vbt.vzo import VZOProX` → `from src.indicators.vzo import VZOProX`
  - `from Pinescript.vbt.signals import generate_signals` → `from src.indicators.signals import generate_signals`
  - Generic pattern: `Pinescript.vbt.` → `src.indicators.`
- **Clean __init__.py exports** — users should only need `from src.indicators import SniperProX` (not deep paths)
- **No changes to VBT dependency** — all indicators still use `vectorbtpro.indicators.factory.IndicatorFactory`

### Existing Import Patterns in Source Code
The current source files use these imports that MUST be updated:

```python
# In sniper.py:
from Pinescript.vbt.nb.ma_library_nb import MA_JURIK, MA_TYPE_NAMES
from Pinescript.vbt.nb.sniper_nb import sniper_core_1d_nb

# In vzo.py:
from Pinescript.vbt.nb.ma_library_nb import MA_JURIK, MA_TYPE_NAMES
from Pinescript.vbt.nb.vzo_nb import vzo_core_1d_nb

# In spectral.py:
from Pinescript.vbt.nb.spectral_nb import spectral_analysis_1d_nb

# In signals.py:
from Pinescript.vbt.sniper import SniperProX
from Pinescript.vbt.vzo import VZOProX

# In backtest.py:
from Pinescript.vbt.signals import generate_signals

# In optimize.py:
from Pinescript.vbt.sniper import SniperProX
from Pinescript.vbt.vzo import VZOProX
from Pinescript.vbt.nb.ma_library_nb import MA_JURIK, MA_HULL, MA_KAMA, MA_EMA, MA_T3

# In nb/__init__.py:
from Pinescript.vbt.nb.ma_library_nb import *

# In __init__.py (package root):
from Pinescript.vbt.ma_library import UniversalMA
from Pinescript.vbt.vzo import VZOProX
from Pinescript.vbt.sniper import SniperProX
from Pinescript.vbt.spectral import SpectralAnalysis
```

---

## Task Layer

### Tasks

1. **Create directory structure**:
   ```
   src/indicators/
   src/indicators/nb/
   ```

2. **Copy and update Numba kernels** — for each file in `nb/`:

   2a. Copy `/home/ai-coder/Projects/vectorbt.pro/Pinescript/vbt/nb/ma_library_nb.py` to `src/indicators/nb/ma_library_nb.py`
   - No import changes needed (only imports from `numba`, `numpy`, `math` — no Pinescript refs)

   2b. Copy `nb/vzo_nb.py` to `src/indicators/nb/vzo_nb.py`
   - Update any `Pinescript.vbt.nb.*` imports to `src.indicators.nb.*`

   2c. Copy `nb/sniper_nb.py` to `src/indicators/nb/sniper_nb.py`
   - Update any `Pinescript.vbt.nb.*` imports to `src.indicators.nb.*`

   2d. Copy `nb/spectral_nb.py` to `src/indicators/nb/spectral_nb.py`
   - Update any `Pinescript.vbt.nb.*` imports to `src.indicators.nb.*`

   2e. Copy `nb/astro_nb.py` to `src/indicators/nb/astro_nb.py`
   - Update any `Pinescript.vbt.nb.*` imports to `src.indicators.nb.*`

   2f. Create `src/indicators/nb/__init__.py`:
   ```python
   """Numba-compiled kernels for indicator calculations."""
   from src.indicators.nb.ma_library_nb import *  # noqa: F401,F403
   ```

3. **Copy and update IndicatorFactory wrappers**:

   3a. Copy `ma_library.py` to `src/indicators/ma_library.py`
   - Replace all `from Pinescript.vbt.nb.` → `from src.indicators.nb.`

   3b. Copy `vzo.py` to `src/indicators/vzo.py`
   - Replace `from Pinescript.vbt.nb.ma_library_nb import ...` → `from src.indicators.nb.ma_library_nb import ...`
   - Replace `from Pinescript.vbt.nb.vzo_nb import ...` → `from src.indicators.nb.vzo_nb import ...`

   3c. Copy `sniper.py` to `src/indicators/sniper.py`
   - Replace `from Pinescript.vbt.nb.ma_library_nb import ...` → `from src.indicators.nb.ma_library_nb import ...`
   - Replace `from Pinescript.vbt.nb.sniper_nb import ...` → `from src.indicators.nb.sniper_nb import ...`

   3d. Copy `spectral.py` to `src/indicators/spectral.py`
   - Replace `from Pinescript.vbt.nb.spectral_nb import ...` → `from src.indicators.nb.spectral_nb import ...`

   3e. Copy `astro_lib.py` to `src/indicators/astro_lib.py`
   - Replace all `Pinescript.vbt.` → `src.indicators.`

   3f. Copy `celestial_channels.py` to `src/indicators/celestial_channels.py`
   - Replace all `Pinescript.vbt.` → `src.indicators.`

4. **Copy and update signal/backtest/optimize**:

   4a. Copy `signals.py` to `src/indicators/signals.py`
   - Replace `from Pinescript.vbt.sniper import SniperProX` → `from src.indicators.sniper import SniperProX`
   - Replace `from Pinescript.vbt.vzo import VZOProX` → `from src.indicators.vzo import VZOProX`

   4b. Copy `backtest.py` to `src/indicators/backtest.py`
   - Replace `from Pinescript.vbt.signals import generate_signals` → `from src.indicators.signals import generate_signals`

   4c. Copy `optimize.py` to `src/indicators/optimize.py`
   - Replace `from Pinescript.vbt.sniper import SniperProX` → `from src.indicators.sniper import SniperProX`
   - Replace `from Pinescript.vbt.vzo import VZOProX` → `from src.indicators.vzo import VZOProX`
   - Replace `from Pinescript.vbt.nb.ma_library_nb import ...` → `from src.indicators.nb.ma_library_nb import ...`

5. **Create `src/indicators/__init__.py`**:
   ```python
   """UpTrade Indicator Engine — ported from VectorBT Pro Pine Script indicators.

   Package structure:
   - nb/          — Numba-compiled kernels
   - ma_library   — 34 MA types (UniversalMA IndicatorFactory)
   - vzo          — VZO-ProX oscillator
   - sniper       — SniperProX indicator
   - spectral     — Spectral Analysis (Hurst + Goertzel)
   - astro_lib    — Astronomical calculations
   - celestial_channels — Planetary channel lines
   - signals      — Combined signal generation
   - backtest     — Portfolio backtesting pipeline
   - optimize     — Parameter grid search
   """

   from src.indicators.ma_library import UniversalMA  # noqa: F401
   from src.indicators.vzo import VZOProX  # noqa: F401
   from src.indicators.sniper import SniperProX  # noqa: F401
   from src.indicators.spectral import SpectralAnalysis  # noqa: F401
   from src.indicators.signals import generate_signals  # noqa: F401
   from src.indicators.backtest import run_backtest  # noqa: F401
   from src.indicators.optimize import optimize_sniper, optimize_vzo  # noqa: F401
   ```

6. **Verify no remaining `Pinescript.vbt` references**:
   - Run `grep -r "Pinescript" src/indicators/` and confirm zero matches
   - Run `grep -r "from Pinescript" src/indicators/` and confirm zero matches

---

## Validation Layer

### Commands
```bash
cd /home/ai-coder/Projects/uptrade

# Verify no Pinescript imports remain
grep -r "Pinescript" src/indicators/ && echo "FAIL: Pinescript references found" || echo "PASS: No Pinescript references"

# Verify all files exist
for f in \
  src/indicators/__init__.py \
  src/indicators/nb/__init__.py \
  src/indicators/nb/ma_library_nb.py \
  src/indicators/nb/vzo_nb.py \
  src/indicators/nb/sniper_nb.py \
  src/indicators/nb/spectral_nb.py \
  src/indicators/nb/astro_nb.py \
  src/indicators/ma_library.py \
  src/indicators/vzo.py \
  src/indicators/sniper.py \
  src/indicators/spectral.py \
  src/indicators/astro_lib.py \
  src/indicators/celestial_channels.py \
  src/indicators/signals.py \
  src/indicators/backtest.py \
  src/indicators/optimize.py; do
  [ -f "$f" ] && echo "OK: $f" || echo "MISSING: $f"
done

# Verify imports resolve (requires vectorbtpro installed)
python3 -c "
from src.indicators import SniperProX, VZOProX, SpectralAnalysis, UniversalMA
print('SniperProX:', SniperProX)
print('VZOProX:', VZOProX)
print('SpectralAnalysis:', SpectralAnalysis)
print('UniversalMA:', UniversalMA)
print('All indicator imports OK')
"

# Verify signals and backtest modules
python3 -c "
from src.indicators import generate_signals, run_backtest, optimize_sniper, optimize_vzo
print('generate_signals:', generate_signals)
print('run_backtest:', run_backtest)
print('optimize_sniper:', optimize_sniper)
print('optimize_vzo:', optimize_vzo)
print('All utility imports OK')
"

# Verify nb kernels have correct import paths
python3 -c "
from src.indicators.nb.ma_library_nb import MA_JURIK, MA_TYPE_NAMES
print(f'MA_JURIK = {MA_JURIK}')
print(f'MA types available: {len(MA_TYPE_NAMES)}')
"

# Count files copied (should be 16 files: 6 in nb/ + 10 at top level)
echo "File count: $(find src/indicators -name '*.py' | wc -l) (expected: 16)"
```

### Success Criteria
- [ ] All 16 `.py` files exist in `src/indicators/` and `src/indicators/nb/`
- [ ] Zero occurrences of `Pinescript` in any file under `src/indicators/`
- [ ] All `from Pinescript.vbt.` imports replaced with `from src.indicators.`
- [ ] `src/indicators/__init__.py` exports: `UniversalMA`, `VZOProX`, `SniperProX`, `SpectralAnalysis`, `generate_signals`, `run_backtest`, `optimize_sniper`, `optimize_vzo`
- [ ] `src/indicators/nb/__init__.py` exports all MA library contents
- [ ] All indicator code is functionally identical to the source (no logic changes, only import paths)
- [ ] Imports resolve without errors when VBT Pro is installed
- [ ] `MA_TYPE_NAMES` dict is accessible from `src.indicators.nb.ma_library_nb`
- [ ] `SniperProX.run()`, `VZOProX.run()`, `SpectralAnalysis.run()` are callable IndicatorFactory instances
