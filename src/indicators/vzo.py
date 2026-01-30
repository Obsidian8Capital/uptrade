"""VZO-ProX (Volume Zone Oscillator) — IndicatorFactory wrapper.

Usage
-----
>>> from src.indicators.vzo import VZOProX
>>> result = VZOProX.run(close, volume, vzo_length=14)
>>> result.vzo        # raw VZO
>>> result.minor_buy  # boolean signal array
"""

import numpy as np

from vectorbtpro.indicators.factory import IndicatorFactory

from src.indicators.nb.ma_library_nb import MA_JURIK, MA_TYPE_NAMES
from src.indicators.nb.vzo_nb import vzo_core_1d_nb


def _resolve_ma(ma_type):
    if isinstance(ma_type, str):
        return MA_TYPE_NAMES.get(ma_type, MA_JURIK)
    return int(ma_type)


def _vzo_apply(
    close, volume,
    vzo_length, ma_type,
    noise_length, phase, power,
    data_sample, pcnt_above, pcnt_below,
    minor_sell_val, minor_buy_val, minor_major_range,
    zero_cross_filter_range,
):
    nrows, ncols = close.shape
    mt = _resolve_ma(ma_type)

    vzo = np.empty_like(close)
    vzo_smooth = np.empty_like(close)
    minor_buy = np.empty_like(close)
    major_buy = np.empty_like(close)
    minor_sell = np.empty_like(close)
    major_sell = np.empty_like(close)

    for col in range(ncols):
        res = vzo_core_1d_nb(
            close[:, col], volume[:, col],
            int(vzo_length), int(noise_length),
            int(mt), float(phase), float(power),
            int(data_sample), float(pcnt_above), float(pcnt_below),
            float(minor_sell_val), float(minor_buy_val),
            float(minor_major_range), float(zero_cross_filter_range),
        )
        vzo[:, col] = res[0]
        vzo_smooth[:, col] = res[1]
        minor_buy[:, col] = res[2]
        major_buy[:, col] = res[3]
        minor_sell[:, col] = res[4]
        major_sell[:, col] = res[5]

    return vzo, vzo_smooth, minor_buy, major_buy, minor_sell, major_sell


VZOProX = IndicatorFactory(
    class_name="VZOProX",
    module_name=__name__,
    input_names=["close", "volume"],
    param_names=["vzo_length", "ma_type"],
    output_names=["vzo", "vzo_smoothed", "minor_buy", "major_buy", "minor_sell", "major_sell"],
    attr_settings=dict(
        close=dict(doc="Close price series."),
        volume=dict(doc="Volume series."),
        vzo=dict(doc="Raw VZO oscillator."),
        vzo_smoothed=dict(doc="Noise-filtered VZO."),
        minor_buy=dict(doc="Minor buy signal (NaN = no signal)."),
        major_buy=dict(doc="Major buy signal (NaN = no signal)."),
        minor_sell=dict(doc="Minor sell signal (NaN = no signal)."),
        major_sell=dict(doc="Major sell signal (NaN = no signal)."),
    ),
).with_apply_func(
    _vzo_apply,
    kwargs_as_args=[
        "noise_length", "phase", "power",
        "data_sample", "pcnt_above", "pcnt_below",
        "minor_sell_val", "minor_buy_val", "minor_major_range",
        "zero_cross_filter_range",
    ],
    param_settings=dict(
        vzo_length=dict(doc="VZO smoothing length."),
        ma_type=dict(doc="MA type string or integer code."),
    ),
    vzo_length=14,
    ma_type="Jurik Moving Average",
    noise_length=2,
    phase=50.0,
    power=2.0,
    data_sample=55,
    pcnt_above=80.0,
    pcnt_below=80.0,
    minor_sell_val=40.0,
    minor_buy_val=-40.0,
    minor_major_range=20.0,
    zero_cross_filter_range=20.0,
)
