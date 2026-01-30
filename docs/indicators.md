# Indicator Reference

## Universal MA Library

The `UniversalMA` indicator wraps all **34 moving average types** from the MovingAverageLibrary, compiled to native code via Numba. Any indicator in the platform can use any MA type by name or integer code.

**Usage:**
```python
from src.indicators.ma_library import UniversalMA

result = UniversalMA.run(close, window=14, ma_type="Jurik Moving Average")
result.ma  # pd.Series
```

### Supported MA Types

| # | Name | Code |
|---|------|------|
| 0 | Simple Moving Average | `MA_SMA` |
| 1 | Exponential Moving Average | `MA_EMA` |
| 2 | Weighted Moving Average | `MA_WMA` |
| 3 | Relative / Smoothed Moving Average (Wilder) | `MA_RMA` |
| 4 | Double Exponential Moving Average | `MA_DEMA` |
| 5 | Triple Exponential Moving Average | `MA_TEMA` |
| 6 | Hull Moving Average | `MA_HULL` |
| 7 | Arnaud Legoux Moving Average | `MA_ALMA` |
| 8 | Jurik Moving Average | `MA_JURIK` |
| 9 | Kaufman's Adaptive Moving Average | `MA_KAMA` |
| 10 | Fractal Adaptive Moving Average | `MA_FRAMA` |
| 11 | Volatility Adjusted Moving Average | `MA_VAMA` |
| 12 | Tilson T3 Moving Average | `MA_T3` |
| 13 | Tilson T3 (early version) Moving Average | `MA_T3_EARLY` |
| 14 | Zero-Lag Exponential Moving Average | `MA_ZLEMA` |
| 15 | McGinley Dynamic | `MA_MCGINLEY` |
| 16 | Modular Filter | `MA_MODULAR_FILTER` |
| 17 | Coefficient of Variation Weighted MA | `MA_COVWMA` |
| 18 | Ehlers Dynamic Smoothed MA | `MA_EDSMA` |
| 19 | Ehlers Super Smoother | `MA_EHLERS_SUPER_SMOOTHER` |
| 20 | Ehlers EMA Smoother | `MA_EHLERS_EMA_SMOOTHER` |
| 21 | Ahrens Moving Average | `MA_AHRENS` |
| 22 | Alexander Moving Average | `MA_ALEXANDER` |
| 23 | Average Directional Volatility MA | `MA_ADXVMA` |
| 24 | Integral of Linear Regression Slope | `MA_ILRS` |
| 25 | Leader Exponential Moving Average | `MA_LEADER_EMA` |
| 26 | Recursive Moving Trendline | `MA_RMTA` |
| 27 | Simple Decycler | `MA_DECYCLER` |
| 28 | Triangular Moving Average | `MA_TRIANGULAR` |
| 29 | Exponential MA Optimized | `MA_XEMA` |
| 30 | Donchian | `MA_DONCHIAN` |
| 31 | Donchian v2 | `MA_DONCHIAN_V2` |
| 32 | Volume Weighted Moving Average | `MA_VWMA` |
| 33 | Least Squares Moving Average | `MA_LINREG` |

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `window` | int | 14 | Lookback window size |
| `ma_type` | str or int | `"Jurik Moving Average"` | MA type name or integer code |
| `phase` | float | 0.0 | Phase parameter (Jurik, EDSMA) |
| `power` | float | 2.0 | Power parameter (Jurik, EDSMA) |

---

## SniperProX

Fisher-transform oscillator with adaptive MA smoothing, DMI/ADX filtering, and volume confirmation. Generates major/minor buy/sell signals and trailing signals.

**Module:** `src/indicators/sniper.py`

**Usage:**
```python
from src.indicators.sniper import SniperProX

result = SniperProX.run(close, high, low, volume, length=28)
result.f3          # Fisher-transformed oscillator
result.major_buy   # NaN where no signal, value at signal bar
result.major_sell  # NaN where no signal, value at signal bar
```

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `length` | int | 28 | 5-200 | Lookback period for the oscillator |
| `ma_type` | str/int | `"Jurik Moving Average"` | Any of 34 types | Smoothing MA type |
| `overbought_oversold` | float | 1.386 | 0.5-3.0 | OB/OS threshold for Fisher transform |
| `trail_threshold` | float | 0.986 | 0.9-1.0 | Trailing signal sensitivity |
| `dmi_len` | int | 14 | 5-50 | DMI/ADX lookback length |
| `adx_thresh` | float | 20.0 | 10-50 | ADX threshold for trend confirmation |
| `vol_avg_len` | int | 20 | 5-100 | Volume average lookback |
| `vol_per_thresh` | float | 50.0 | 10-100 | Volume percentile threshold |
| `phase` | float | 0.0 | -100-100 | Jurik MA phase parameter |
| `power` | float | 2.0 | 0.5-5.0 | Jurik MA power parameter |
| `data_sample` | int | 55 | 10-200 | Adaptive zone sample size |
| `pcnt_above` | float | 88.0 | 50-99 | Upper adaptive zone percentile |
| `pcnt_below` | float | 88.0 | 50-99 | Lower adaptive zone percentile |

### Outputs

| Output | Description |
|--------|-------------|
| `f3` | Fisher-transformed oscillator value |
| `sc` | Ready/Aim state counter |
| `minor_buy` | Minor buy signal (NaN = no signal) |
| `major_buy` | Major buy signal with Aim confirmation (NaN = no signal) |
| `minor_sell` | Minor sell signal (NaN = no signal) |
| `major_sell` | Major sell signal with Aim confirmation (NaN = no signal) |
| `buy_trail` | Trailing long signal |
| `sell_trail` | Trailing short signal |
| `adaptive_cross_up` | Adaptive zone cross up |
| `adaptive_cross_down` | Adaptive zone cross down |

### Signal Logic

1. The Fisher transform normalizes the oscillator into a bounded range.
2. **Minor signals** fire when the oscillator crosses the OB/OS threshold.
3. **Major signals** require additional confirmation from the Ready/Aim state machine (the `sc` counter must reach the Aim state) combined with DMI/ADX trend filtering and volume confirmation.
4. **Trailing signals** track exits using the `trail_threshold` parameter.
5. **Adaptive zones** dynamically adjust the signal thresholds based on recent price distribution.

---

## VZOProX

Volume Zone Oscillator with noise filtering and adaptive zone signals. Measures buying vs. selling pressure through volume-price relationship.

**Module:** `src/indicators/vzo.py`

**Usage:**
```python
from src.indicators.vzo import VZOProX

result = VZOProX.run(close, volume, vzo_length=14)
result.vzo          # Raw VZO oscillator
result.vzo_smoothed # Noise-filtered VZO
result.major_buy    # NaN where no signal
```

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `vzo_length` | int | 14 | 5-100 | VZO smoothing length |
| `ma_type` | str/int | `"Jurik Moving Average"` | Any of 34 types | Smoothing MA type |
| `noise_length` | int | 2 | 1-10 | Noise filter length |
| `phase` | float | 50.0 | -100-100 | Jurik MA phase parameter |
| `power` | float | 2.0 | 0.5-5.0 | Jurik MA power parameter |
| `data_sample` | int | 55 | 10-200 | Adaptive zone sample size |
| `pcnt_above` | float | 80.0 | 50-99 | Upper adaptive zone percentile |
| `pcnt_below` | float | 80.0 | 50-99 | Lower adaptive zone percentile |
| `minor_sell_val` | float | 40.0 | 10-80 | Minor sell zone threshold |
| `minor_buy_val` | float | -40.0 | -80 to -10 | Minor buy zone threshold |
| `minor_major_range` | float | 20.0 | 5-50 | Range between minor and major signals |
| `zero_cross_filter_range` | float | 20.0 | 5-50 | Zero-cross filter width |

### Outputs

| Output | Description |
|--------|-------------|
| `vzo` | Raw VZO oscillator value |
| `vzo_smoothed` | Noise-filtered VZO |
| `minor_buy` | Minor buy signal (NaN = no signal) |
| `major_buy` | Major buy signal (NaN = no signal) |
| `minor_sell` | Minor sell signal (NaN = no signal) |
| `major_sell` | Major sell signal (NaN = no signal) |

### Signal Logic

1. VZO measures volume flow direction: positive = buying pressure, negative = selling pressure.
2. **Minor signals** trigger when VZO crosses the `minor_buy_val` / `minor_sell_val` thresholds.
3. **Major signals** require VZO to reach `minor_buy_val - minor_major_range` (buy) or `minor_sell_val + minor_major_range` (sell), with zero-cross filtering to reduce whipsaws.

---

## Spectral Analysis

Multi-cycle spectral decomposition using Hurst Bandpass Filter (IIR) or Goertzel Algorithm (DFT). Detects 11 predefined cycle periods from 5-day to 18-year.

**Module:** `src/indicators/spectral.py`

**Usage:**
```python
from src.indicators.spectral import SpectralAnalysis

result = SpectralAnalysis.run(source, method=0)  # 0=Hurst, 1=Goertzel
result.composite   # Composite cycle sum
```

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `method` | int | 0 | 0-1 | Detection method: 0 = Hurst Bandpass, 1 = Goertzel DFT |
| `bandwidth` | float | 0.025 | 0.001-0.1 | Bandpass filter bandwidth |
| `window_size` | int | 618 | 100-2000 | Analysis window size |
| `scale_factor` | float | 100000.0 | 1-1e6 | Output scaling factor |

### Predefined Cycle Periods

| Cycle Name | Period (bars) | Approximate Duration |
|------------|---------------|---------------------|
| 5d | 4.3 | 5 trading days |
| 10d | 8.5 | 10 trading days |
| 20d | 17.0 | 20 trading days |
| 40d | 34.1 | 40 trading days |
| 80d | 68.2 | 80 trading days |
| 20w | 136.4 | 20 weeks |
| 40w | 272.8 | 40 weeks |
| 18m | 545.6 | 18 months |
| 54m | 1636.8 | 54 months |
| 9y | 3273.6 | 9 years |
| 18y | 6547.2 | 18 years |

### Multi-Timeframe Cycle Detector

The `MTFCycleDetector` class (`src/indicators/mtf_cycles.py`) runs spectral analysis across multiple timeframes and computes a power-weighted composite score.

```python
from src.indicators.mtf_cycles import MTFCycleDetector

detector = MTFCycleDetector(symbol="X:BTCUSD", timeframes=["5m", "1h", "4h", "1d"])
result = detector.run(data)  # data = {timeframe: DataFrame}
print(result["composite_score"])    # Power-weighted average period
print(result["suggested_length"])   # Suggested indicator lookback
```

---

## AstroLib

Financial astrology library providing planetary position calculations, zodiac classification, and aspect detection.

**Module:** `src/indicators/astro_lib.py`

Key features:
- Julian Date conversions
- Sun, Moon, and planet ecliptic longitude calculations
- Zodiac sign and Nakshatra classification
- Aspect detection (conjunction, sextile, square, trine, opposition)
- Planet longitude time series generation

```python
from src.indicators.astro_lib import planet_longitude_series, get_zodiac, get_aspect

# Compute Mercury longitude for each bar
longitudes = planet_longitude_series(timestamps_ms, pnum=2)

# Get zodiac position
sign, deg, minutes = get_zodiac(longitudes[-1])

# Check aspect between two planets
aspect = get_aspect(lon_mercury, lon_venus, orb=6.0)
```

---

## Celestial Channels

Converts planetary ecliptic longitude into price-level support/resistance grids.

**Module:** `src/indicators/celestial_channels.py`

```python
from src.indicators.celestial_channels import celestial_channel_levels

levels = celestial_channel_levels(
    timestamps_ms,
    pnum=2,           # Mercury
    scaler=16.18,     # Dollars per degree
    base=6,           # Base harmonic offset
    n_harmonics=10,   # Number of harmonic levels
)
# levels is a DataFrame with columns "h0" through "h9"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pnum` | int | 2 | Planet number (see `astro_lib.PLANET_NUMBERS`) |
| `scaler` | float | 16.18 | Dollars per degree of longitude |
| `base` | int | 6 | Base harmonic offset |
| `n_harmonics` | int | 10 | Number of harmonic levels to generate |
| `mirror` | bool | False | Negate longitude before scaling |
| `pnum_b` | int or None | None | Second planet for midpoint calculation |

---

## Signal Combiner

Combines signals from multiple indicators into a single actionable signal array with four modes.

**Module:** `src/signals/combiner.py`

### Combination Modes

| Mode | Description |
|------|-------------|
| **AND** | All indicators must agree on direction. Most conservative. |
| **OR** | Any non-zero signal triggers; conflicts resolved by majority vote. |
| **WEIGHTED** | Weighted sum of signals compared to a threshold. |
| **CONFIRM** | Primary indicator signals, secondary must confirm within a time window. |

### Usage

```python
from src.signals.combiner import SignalCombiner, SignalCombinerConfig, IndicatorSignalConfig, CombineMode

# Simple AND mode
combiner = SignalCombiner(mode="and")
combined = combiner.combine({
    "sniper": sniper_signals,  # np.ndarray of {-1, 0, 1}
    "vzo": vzo_signals,
})

# Weighted mode with config
config = SignalCombinerConfig(
    mode=CombineMode.WEIGHTED,
    indicators=[
        IndicatorSignalConfig(name="sniper", weight=2.0),
        IndicatorSignalConfig(name="vzo", weight=1.0),
    ],
    weighted_threshold=0.5,
)
combiner = SignalCombiner(config=config)
combined = combiner.combine(signals)

# CONFIRM mode
config = SignalCombinerConfig(
    mode=CombineMode.CONFIRM,
    indicators=[
        IndicatorSignalConfig(name="sniper", role="primary"),
        IndicatorSignalConfig(name="vzo", role="secondary"),
    ],
    confirm_window=3,
)
combiner = SignalCombiner(config=config)
combined = combiner.combine(signals)
```

### Converting Indicator Output

```python
# Convert VBT indicator result to integer signal array
signal_array = SignalCombiner.convert_indicator_output(
    sniper_result,
    signal_source="major"  # "major", "minor", or "composite"
)
```
