"""SniperProX indicator — IndicatorFactory wrapper.

Usage
-----
>>> from src.indicators.sniper import SniperProX
>>> result = SniperProX.run(close, high, low, volume, length=28)
>>> result.f3          # Fisher-transformed oscillator
>>> result.major_buy   # NaN where no signal, value at signal
"""

import numpy as np

from vectorbtpro.indicators.factory import IndicatorFactory

from src.indicators.nb.ma_library_nb import MA_JURIK, MA_TYPE_NAMES
from src.indicators.nb.sniper_nb import sniper_core_1d_nb


def _resolve_ma(ma_type):
    if isinstance(ma_type, str):
        return MA_TYPE_NAMES.get(ma_type, MA_JURIK)
    return int(ma_type)


def _sniper_apply(
    close, high, low, volume,
    length, ma_type,
    overbought_oversold, trail_threshold,
    dmi_len, adx_thresh, vol_avg_len, vol_per_thresh,
    phase, power,
    data_sample, pcnt_above, pcnt_below,
):
    nrows, ncols = close.shape
    mt = _resolve_ma(ma_type)

    f3 = np.empty_like(close)
    sc = np.empty_like(close)
    minor_buy = np.empty_like(close)
    major_buy = np.empty_like(close)
    minor_sell = np.empty_like(close)
    major_sell = np.empty_like(close)
    buy_trail = np.empty_like(close)
    sell_trail = np.empty_like(close)
    adaptive_cross_up = np.empty_like(close)
    adaptive_cross_down = np.empty_like(close)

    for col in range(ncols):
        res = sniper_core_1d_nb(
            close[:, col], high[:, col], low[:, col], volume[:, col],
            int(length), float(overbought_oversold), float(trail_threshold),
            int(dmi_len), float(adx_thresh), int(vol_avg_len), float(vol_per_thresh),
            int(mt), float(phase), float(power),
            int(data_sample), float(pcnt_above), float(pcnt_below),
        )
        f3[:, col] = res[0]
        sc[:, col] = res[1]
        minor_buy[:, col] = res[2]
        major_buy[:, col] = res[3]
        minor_sell[:, col] = res[4]
        major_sell[:, col] = res[5]
        buy_trail[:, col] = res[6]
        sell_trail[:, col] = res[7]
        adaptive_cross_up[:, col] = res[8]
        adaptive_cross_down[:, col] = res[9]

    return (f3, sc, minor_buy, major_buy, minor_sell, major_sell,
            buy_trail, sell_trail, adaptive_cross_up, adaptive_cross_down)


SniperProX = IndicatorFactory(
    class_name="SniperProX",
    module_name=__name__,
    input_names=["close", "high", "low", "volume"],
    param_names=["length", "ma_type"],
    output_names=[
        "f3", "sc",
        "minor_buy", "major_buy", "minor_sell", "major_sell",
        "buy_trail", "sell_trail",
        "adaptive_cross_up", "adaptive_cross_down",
    ],
    attr_settings=dict(
        close=dict(doc="Close price series."),
        high=dict(doc="High price series."),
        low=dict(doc="Low price series."),
        volume=dict(doc="Volume series."),
        f3=dict(doc="Fisher-transformed oscillator."),
        sc=dict(doc="Ready/Aim state counter."),
        minor_buy=dict(doc="Minor buy signal."),
        major_buy=dict(doc="Major buy signal (with Aim confirmation)."),
        minor_sell=dict(doc="Minor sell signal."),
        major_sell=dict(doc="Major sell signal (with Aim confirmation)."),
        buy_trail=dict(doc="Trailing long signal."),
        sell_trail=dict(doc="Trailing short signal."),
        adaptive_cross_up=dict(doc="Adaptive zone cross up."),
        adaptive_cross_down=dict(doc="Adaptive zone cross down."),
    ),
).with_apply_func(
    _sniper_apply,
    kwargs_as_args=[
        "overbought_oversold", "trail_threshold",
        "dmi_len", "adx_thresh", "vol_avg_len", "vol_per_thresh",
        "phase", "power",
        "data_sample", "pcnt_above", "pcnt_below",
    ],
    param_settings=dict(
        length=dict(doc="SniperProX lookback length."),
        ma_type=dict(doc="MA type string or integer code."),
    ),
    length=28,
    ma_type="Jurik Moving Average",
    overbought_oversold=1.386,
    trail_threshold=0.986,
    dmi_len=14,
    adx_thresh=20.0,
    vol_avg_len=20,
    vol_per_thresh=50.0,
    phase=0.0,
    power=2.0,
    data_sample=55,
    pcnt_above=88.0,
    pcnt_below=88.0,
)
