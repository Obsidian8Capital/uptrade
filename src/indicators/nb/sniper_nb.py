"""Numba kernels for SniperProX indicator."""

import numpy as np
from numba import njit

from src.indicators.nb.ma_library_nb import universal_ma_1d_nb, ema_1d_nb, MA_JURIK
from src.indicators.nb.vzo_nb import _percentile_nearest_rank_1d


@njit(cache=True)
def _stoch_1d(close, high, low, length):
    """Stochastic %K."""
    n = close.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        hh = high[i]
        ll = low[i]
        for j in range(1, min(i + 1, length)):
            if high[i - j] > hh:
                hh = high[i - j]
            if low[i - j] < ll:
                ll = low[i - j]
        rng = hh - ll
        out[i] = 100.0 * (close[i] - ll) / rng if rng != 0.0 else 50.0
    return out


@njit(cache=True)
def _true_range_1d(high, low, close):
    n = high.shape[0]
    out = np.empty(n, dtype=np.float64)
    out[0] = high[0] - low[0]
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        out[i] = max(hl, max(hc, lc))
    return out


@njit(cache=True)
def sniper_core_1d_nb(
    close, high, low, volume,
    pro_length, overbought_oversold, trail_threshold,
    dmi_len, adx_thresh, vol_avg_len, vol_per_thresh,
    ma_type, phase, power,
    data_sample, pcnt_above, pcnt_below,
):
    n = close.shape[0]

    # --- Triple-smoothed stochastic k1v, k2v, k3v ---
    stoch5 = _stoch_1d(close, high, low, 5)
    stoch8 = _stoch_1d(close, high, low, 8)
    stoch17 = _stoch_1d(close, high, low, 17)

    k1_raw = universal_ma_1d_nb(stoch5, 3, ma_type, phase, power)
    k2_raw = universal_ma_1d_nb(stoch8, 5, ma_type, phase, power)
    k3_raw = universal_ma_1d_nb(stoch17, 5, ma_type, phase, power)

    k1v = np.empty(n, dtype=np.float64)
    k2v = np.empty(n, dtype=np.float64)
    k3v = np.empty(n, dtype=np.float64)
    for i in range(n):
        k1v[i] = (max(-100.0, min(100.0, k1_raw[i])) - 50.0) / 50.01
        k2v[i] = (max(-100.0, min(100.0, k2_raw[i])) - 50.0) / 50.01
        k3v[i] = (max(-100.0, min(100.0, k3_raw[i])) - 50.0) / 50.01

    # --- Triple MA (TEMA-like with custom MA) ---
    ema1 = universal_ma_1d_nb(close, pro_length, ma_type, phase, power)
    ema2 = universal_ma_1d_nb(ema1, pro_length, ma_type, phase, power)
    ema3 = universal_ma_1d_nb(ema2, pro_length, ma_type, phase, power)
    tavg = np.empty(n, dtype=np.float64)
    for i in range(n):
        tavg[i] = 3.0 * ema1[i] - 3.0 * ema2[i] + ema3[i]

    savg_length = max(int(pro_length / 2), 1)
    matr_raw = _true_range_1d(high, low, close)
    matr = np.empty(n, dtype=np.float64)
    for i in range(n):
        matr[i] = 0.5 * matr_raw[i]

    savgstate = np.zeros(n, dtype=np.float64)
    for i in range(savg_length, n):
        savg = tavg[i - savg_length]
        if low[i] > savg + matr[i]:
            savgstate[i] = 1.0
        elif high[i] < savg - matr[i]:
            savgstate[i] = -1.0

    # --- ADX/DMI ---
    tr = _true_range_1d(high, low, close)
    tr_smooth = universal_ma_1d_nb(tr, dmi_len, ma_type, phase, power)

    up_move = np.empty(n, dtype=np.float64)
    down_move = np.empty(n, dtype=np.float64)
    up_move[0] = 0.0
    down_move[0] = 0.0
    for i in range(1, n):
        up_move[i] = high[i] - high[i - 1]
        down_move[i] = -(low[i] - low[i - 1])

    pdm_src = np.empty(n, dtype=np.float64)
    mdm_src = np.empty(n, dtype=np.float64)
    for i in range(n):
        pdm_src[i] = up_move[i] if (up_move[i] > down_move[i] and up_move[i] > 0) else 0.0
        mdm_src[i] = down_move[i] if (down_move[i] > up_move[i] and down_move[i] > 0) else 0.0

    pdm_smooth = universal_ma_1d_nb(pdm_src, dmi_len, ma_type, phase, power)
    mdm_smooth = universal_ma_1d_nb(mdm_src, dmi_len, ma_type, phase, power)

    dip = np.empty(n, dtype=np.float64)
    dim = np.empty(n, dtype=np.float64)
    adx_src = np.empty(n, dtype=np.float64)
    for i in range(n):
        dip[i] = 100.0 * pdm_smooth[i] / tr_smooth[i] if tr_smooth[i] != 0 else 0.0
        dim[i] = 100.0 * mdm_smooth[i] / tr_smooth[i] if tr_smooth[i] != 0 else 0.0
        s = dip[i] + dim[i]
        adx_src[i] = abs(dip[i] - dim[i]) / s if s != 0 else 0.0
    adx = universal_ma_1d_nb(adx_src, dmi_len, ma_type, phase, power)
    for i in range(n):
        adx[i] *= 100.0

    long_trend = np.zeros(n, dtype=np.float64)
    short_trend = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if dip[i] > dim[i] and adx[i] > adx_thresh:
            long_trend[i] = 1.0
        if dim[i] > dip[i] and adx[i] > adx_thresh:
            short_trend[i] = 1.0

    # Volume strength
    a_vol = universal_ma_1d_nb(volume, vol_avg_len, ma_type, phase, power)
    p_vol = np.empty(n, dtype=np.float64)
    for i in range(1, n):
        p_vol[i] = 100.0 * (volume[i] - a_vol[i - 1]) / volume[i] if volume[i] != 0 else 0.0
    p_vol[0] = 0.0

    # --- SC counter (Ready/Aim state) ---
    SC = np.zeros(n, dtype=np.float64)
    for i in range(2, n):
        if k2v[i] > 0:
            count_chg = -1.0 if (k1v[i] <= k2v[i] and k1v[i - 1] > k2v[i - 1] and k2v[i - 1] > 0) else 0.0
            SC[i] = min(SC[i - 1] if SC[i - 1] < 0 else 0.0, 0.0) + count_chg
        else:
            count_chg = 1.0 if (k1v[i] >= k2v[i] and k1v[i - 1] < k2v[i - 1] and k2v[i - 1] <= 0) else 0.0
            SC[i] = max(SC[i - 1] if SC[i - 1] > 0 else 0.0, 0.0) + count_chg

    # --- Fisher Transform (f3) ---
    f3 = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        k = k3v[i]
        k = max(-0.999, min(0.999, k))
        raw = 0.5 * (np.log((1.0 + k) / (1.0 - k)) + f3[i - 1])
        if np.isnan(raw) or np.isinf(raw):
            f3[i] = f3[i - 1]
        else:
            f3[i] = raw

    # --- Dynamic Zone ---
    smpl_above = _percentile_nearest_rank_1d(f3, data_sample, pcnt_above)
    smpl_below = _percentile_nearest_rank_1d(f3, data_sample, 100.0 - pcnt_below)

    # --- Signals ---
    major = np.empty(n, dtype=np.float64)
    for i in range(n):
        major[i] = f3[i]

    minor_buy = np.full(n, np.nan)
    major_buy = np.full(n, np.nan)
    minor_sell = np.full(n, np.nan)
    major_sell = np.full(n, np.nan)
    buy_trail = np.full(n, np.nan)
    sell_trail = np.full(n, np.nan)
    adaptive_cross_up = np.zeros(n, dtype=np.float64)
    adaptive_cross_down = np.zeros(n, dtype=np.float64)

    for i in range(2, n):
        s0 = np.sign(f3[i] - f3[i - 1])
        s1 = np.sign(f3[i - 1] - f3[i - 2])

        if s0 > s1 and major[i] < -overbought_oversold:
            minor_buy[i] = f3[i - 1]
        if s0 > s1 and major[i] < -overbought_oversold and SC[i] > 1:
            major_buy[i] = f3[i - 1]

        if s0 < s1 and major[i] > overbought_oversold:
            minor_sell[i] = f3[i - 1]
        if s0 < s1 and major[i] > overbought_oversold and SC[i] < -1:
            major_sell[i] = f3[i - 1]

        if s0 > s1 and major[i] > trail_threshold:
            buy_trail[i] = f3[i - 1]
        if s0 < s1 and major[i] < -trail_threshold:
            sell_trail[i] = f3[i - 1]

        if major[i] >= smpl_below[i] and major[i - 1] < smpl_below[i] and (major[i - 2] - major[i]) < -0.01:
            adaptive_cross_up[i] = 1.0
        if major[i] <= smpl_above[i] and major[i - 1] > smpl_above[i] and (major[i - 2] - major[i]) > 0.01:
            adaptive_cross_down[i] = 1.0

    return (
        f3, SC,
        minor_buy, major_buy, minor_sell, major_sell,
        buy_trail, sell_trail,
        adaptive_cross_up, adaptive_cross_down,
        smpl_above, smpl_below,
        long_trend, short_trend,
    )
