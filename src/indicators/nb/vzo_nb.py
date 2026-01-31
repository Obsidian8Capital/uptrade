"""Numba kernels for VZO-ProX (Volume Zone Oscillator)."""

import numpy as np
from numba import njit

from src.indicators.nb.ma_library_nb import universal_ma_1d_nb


@njit(cache=True)
def _percentile_nearest_rank_1d(src, sample_len, percentile):
    """Rolling percentile via nearest-rank method."""
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        length = min(i + 1, sample_len)
        buf = np.empty(length, dtype=np.float64)
        for j in range(length):
            buf[j] = src[i - j]
        buf.sort()
        rank = int(np.ceil(percentile / 100.0 * length)) - 1
        rank = max(0, min(rank, length - 1))
        out[i] = buf[rank]
    return out


@njit(cache=True)
def vzo_core_1d_nb(
    close,
    volume,
    vzo_length,
    noise_length,
    ma_type,
    phase,
    power,
    data_sample,
    pcnt_above,
    pcnt_below,
    minor_sell_val,
    minor_buy_val,
    minor_major_range,
    zero_cross_filter_range,
):
    """Compute VZO-ProX outputs for a single column.

    Returns
    -------
    tuple of 1-D arrays:
        vzo, vzo_smoothed,
        minor_buy, major_buy, minor_sell, major_sell,
        zero_cross_up, zero_cross_down,
        adaptive_cross_up, adaptive_cross_down,
        adaptive_buy, adaptive_sell,
        smpl_above, smpl_below
    """
    n = close.shape[0]

    # Signed volume
    signed_vol = np.empty(n, dtype=np.float64)
    signed_vol[0] = 0.0
    for i in range(1, n):
        diff = close[i] - close[i - 1]
        sign = 1.0 if diff > 0 else (-1.0 if diff < 0 else 0.0)
        signed_vol[i] = sign * volume[i]

    # VP and TV
    vp = universal_ma_1d_nb(signed_vol, vzo_length, ma_type, phase, power)
    tv = universal_ma_1d_nb(volume, vzo_length, ma_type, phase, power)

    # TurboVZO
    turbo_vzo = np.empty(n, dtype=np.float64)
    for i in range(n):
        turbo_vzo[i] = 100.0 * vp[i] / tv[i] if tv[i] != 0.0 else 0.0

    # Smoothed VZO
    turbo_vzo_e = universal_ma_1d_nb(turbo_vzo, noise_length, ma_type, phase, power)

    # Adaptive zones
    smpl_above = _percentile_nearest_rank_1d(turbo_vzo, data_sample, pcnt_above)
    smpl_below = _percentile_nearest_rank_1d(turbo_vzo, data_sample, 100.0 - pcnt_below)

    # Signals
    minor_buy = np.full(n, np.nan)
    major_buy = np.full(n, np.nan)
    minor_sell = np.full(n, np.nan)
    major_sell = np.full(n, np.nan)
    zero_cross_up = np.zeros(n, dtype=np.float64)
    zero_cross_down = np.zeros(n, dtype=np.float64)
    adaptive_cross_up = np.zeros(n, dtype=np.float64)
    adaptive_cross_down = np.zeros(n, dtype=np.float64)
    adaptive_buy = np.full(n, np.nan)
    adaptive_sell = np.full(n, np.nan)

    for i in range(2, n):
        v0 = turbo_vzo[i]
        v1 = turbo_vzo[i - 1]
        v2 = turbo_vzo[i - 2]
        ve = turbo_vzo_e[i]
        s0 = np.sign(v0 - v1)
        s1 = np.sign(v1 - v2)

        # Turning-point buy signals
        if s0 > s1 and v0 < minor_buy_val:
            minor_buy[i] = v1
        if s0 > s1 and v0 < minor_buy_val - minor_major_range:
            major_buy[i] = v1

        # Turning-point sell signals
        if s0 < s1 and v0 > minor_sell_val:
            minor_sell[i] = v1
        if s0 < s1 and v0 > minor_sell_val + minor_major_range:
            major_sell[i] = v1

        # Zero line crosses
        if v0 >= 0.0 and v1 < 0.0 and (ve - v2) > zero_cross_filter_range:
            zero_cross_up[i] = 1.0
        if v0 <= 0.0 and v1 > 0.0 and (v2 - ve) > zero_cross_filter_range:
            zero_cross_down[i] = 1.0

        # Adaptive zone crosses
        if v0 >= smpl_below[i] and v1 < smpl_below[i] and (ve - v2) > zero_cross_filter_range:
            adaptive_cross_up[i] = 1.0
        if v0 <= smpl_above[i] and v1 > smpl_above[i] and (v2 - ve) > zero_cross_filter_range:
            adaptive_cross_down[i] = 1.0

        # Adaptive zone buy/sell
        if s0 > s1 and v0 < smpl_below[i]:
            adaptive_buy[i] = v1
        if s0 < s1 and v0 > smpl_above[i]:
            adaptive_sell[i] = v1

    return (
        turbo_vzo, turbo_vzo_e,
        minor_buy, major_buy, minor_sell, major_sell,
        zero_cross_up, zero_cross_down,
        adaptive_cross_up, adaptive_cross_down,
        adaptive_buy, adaptive_sell,
        smpl_above, smpl_below,
    )
