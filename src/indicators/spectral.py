"""Spectral Analysis Oscillator — IndicatorFactory wrapper.

Two detection methods:
- **Hurst** Bandpass Filter (IIR)
- **Goertzel** Algorithm (DFT at specific frequency)

11 cycle periods from 5-day to 18-year.

Usage
-----
>>> from src.indicators.spectral import SpectralAnalysis
>>> result = SpectralAnalysis.run(source, method=0)  # 0=Hurst, 1=Goertzel
>>> result.composite   # composite cycle sum
>>> result.cycles      # (n, 11) individual cycles as 2-D output
"""

import numpy as np

from vectorbtpro.indicators.factory import IndicatorFactory

from src.indicators.nb.spectral_nb import spectral_analysis_1d_nb

# Default cycle periods (in bars) matching Pine Script inputs
DEFAULT_PERIODS = np.array([
    4.3,     # 5 Day
    8.5,     # 10 Day
    17.0,    # 20 Day
    34.1,    # 40 Day
    68.2,    # 80 Day
    136.4,   # 20 Week
    272.8,   # 40 Week
    545.6,   # 18 Month
    1636.8,  # 54 Month
    3273.6,  # 9 Year
    6547.2,  # 18 Year
], dtype=np.float64)

CYCLE_NAMES = [
    "5d", "10d", "20d", "40d", "80d",
    "20w", "40w", "18m", "54m", "9y", "18y",
]


def _spectral_apply(source, method, bandwidth, window_size, scale_factor):
    nrows, ncols = source.shape
    composite_out = np.empty_like(source)

    composite_mask = np.ones(len(DEFAULT_PERIODS), dtype=np.bool_)

    for col in range(ncols):
        cycles, composite = spectral_analysis_1d_nb(
            source[:, col],
            DEFAULT_PERIODS,
            composite_mask,
            float(bandwidth),
            int(method),
            int(window_size),
            float(scale_factor),
        )
        composite_out[:, col] = composite

    return (composite_out,)


SpectralAnalysis = IndicatorFactory(
    class_name="SpectralAnalysis",
    module_name=__name__,
    input_names=["source"],
    param_names=["method"],
    output_names=["composite"],
    attr_settings=dict(
        source=dict(doc="Price source series (e.g., hl2)."),
        composite=dict(doc="Composite cycle sum."),
    ),
).with_apply_func(
    _spectral_apply,
    kwargs_as_args=["bandwidth", "window_size", "scale_factor"],
    param_settings=dict(
        method=dict(doc="Detection method: 0 = Hurst, 1 = Goertzel."),
    ),
    method=0,
    bandwidth=0.025,
    window_size=618,
    scale_factor=100000.0,
)
