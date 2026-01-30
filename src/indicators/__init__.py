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

from src.indicators.mtf_cycles import MTFCycleDetector, detect_cycles  # noqa: F401
