"""Numba-compiled moving average kernels.

Ports all 34 MA types from MovingAverageLibrary.txt (Pine Script) to @njit functions.
MA types already in VBT (Simple, Weighted, Exp, Wilder, Vidya) are re-used via
the built-in ``vbt.MA`` where possible, but standalone @njit versions are also
provided here so the universal dispatcher can run entirely inside Numba.
"""

import numpy as np
from numba import njit

# ---------------------------------------------------------------------------
# MA Type enum (plain ints for Numba compatibility)
# ---------------------------------------------------------------------------
MA_SMA = 0
MA_EMA = 1
MA_WMA = 2
MA_RMA = 3      # Wilder / SMMA
MA_DEMA = 4
MA_TEMA = 5
MA_HULL = 6
MA_ALMA = 7
MA_JURIK = 8
MA_KAMA = 9
MA_FRAMA = 10
MA_VAMA = 11
MA_T3 = 12
MA_T3_EARLY = 13
MA_ZLEMA = 14
MA_MCGINLEY = 15
MA_MODULAR_FILTER = 16
MA_COVWMA = 17
MA_EDSMA = 18
MA_EHLERS_SUPER_SMOOTHER = 19
MA_EHLERS_EMA_SMOOTHER = 20
MA_AHRENS = 21
MA_ALEXANDER = 22
MA_ADXVMA = 23
MA_ILRS = 24
MA_LEADER_EMA = 25
MA_RMTA = 26
MA_DECYCLER = 27
MA_TRIANGULAR = 28
MA_XEMA = 29
MA_DONCHIAN = 30
MA_DONCHIAN_V2 = 31
MA_VWMA = 32
MA_LINREG = 33

# Mapping from string names (matching Pine Script options) to int codes
MA_TYPE_NAMES = {
    "Simple Moving Average": MA_SMA,
    "Exponential Moving Average": MA_EMA,
    "Weighted Moving Average": MA_WMA,
    "Relative Moving Average": MA_RMA,
    "Smoothed Moving Average": MA_RMA,
    "Double Exponential Moving Average": MA_DEMA,
    "Triple Exponential Moving Average": MA_TEMA,
    "Hull Moving Average": MA_HULL,
    "Arnaud Legoux Moving Average": MA_ALMA,
    "Jurik Moving Average": MA_JURIK,
    "Kaufman's Adaptive Moving Average": MA_KAMA,
    "Fractal Adaptive Moving Average": MA_FRAMA,
    "Volatility Adjusted Moving Average": MA_VAMA,
    "Tilson T3 Moving Average": MA_T3,
    "Tilson T3(early version) Moving Average": MA_T3_EARLY,
    "Zero-Lag Exponential Moving Average": MA_ZLEMA,
    "McGinley": MA_MCGINLEY,
    "Modular Filter": MA_MODULAR_FILTER,
    "Coefficient of Variation Weighted Moving Average": MA_COVWMA,
    "Ehlers Dynamic Smoothed Moving Average": MA_EDSMA,
    "Ehlers EMA Smoother": MA_EHLERS_EMA_SMOOTHER,
    "Ahrens Moving Average": MA_AHRENS,
    "Alexander Moving Average": MA_ALEXANDER,
    "Average Directional Volatility Moving Average": MA_ADXVMA,
    "Integral of Linear Regression Slope": MA_ILRS,
    "Leader Exponential Moving Average": MA_LEADER_EMA,
    "Recursive Moving Trendline": MA_RMTA,
    "Simple Decycler": MA_DECYCLER,
    "Triangular Moving Average": MA_TRIANGULAR,
    "Exponential Moving Average Optimized": MA_XEMA,
    "Donchian": MA_DONCHIAN,
    "Donchian v2": MA_DONCHIAN_V2,
    "Volume Weighted Moving Average": MA_VWMA,
    "Least Squares Moving Average": MA_LINREG,
    "Ehlers Super Smoother": MA_EHLERS_SUPER_SMOOTHER,
}


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------
@njit(cache=True)
def _nz(val, default=0.0):
    return default if np.isnan(val) else val


# ---------------------------------------------------------------------------
# Simple Moving Average
# ---------------------------------------------------------------------------
@njit(cache=True)
def sma_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    cumsum = 0.0
    for i in range(n):
        cumsum += src[i]
        if i >= window:
            cumsum -= src[i - window]
        if i < window - 1:
            out[i] = np.nan
        else:
            out[i] = cumsum / window
    return out


# ---------------------------------------------------------------------------
# Exponential Moving Average
# ---------------------------------------------------------------------------
@njit(cache=True)
def ema_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    alpha = 2.0 / (window + 1.0)
    # seed with first value
    out[0] = src[0]
    for i in range(1, n):
        out[i] = alpha * src[i] + (1.0 - alpha) * out[i - 1]
    return out


# ---------------------------------------------------------------------------
# Weighted Moving Average
# ---------------------------------------------------------------------------
@njit(cache=True)
def wma_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    denom = window * (window + 1) / 2.0
    for i in range(n):
        if i < window - 1:
            out[i] = np.nan
        else:
            s = 0.0
            for j in range(window):
                s += src[i - window + 1 + j] * (j + 1)
            out[i] = s / denom
    return out


# ---------------------------------------------------------------------------
# Wilder / RMA / SMMA
# ---------------------------------------------------------------------------
@njit(cache=True)
def rma_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    # seed with SMA
    s = 0.0
    for i in range(min(window, n)):
        s += src[i]
        out[i] = np.nan
    if n >= window:
        out[window - 1] = s / window
        for i in range(window, n):
            out[i] = (out[i - 1] * (window - 1) + src[i]) / window
    return out


# ---------------------------------------------------------------------------
# Double EMA
# ---------------------------------------------------------------------------
@njit(cache=True)
def dema_1d_nb(src, window):
    e1 = ema_1d_nb(src, window)
    e2 = ema_1d_nb(e1, window)
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        out[i] = 2.0 * e1[i] - e2[i]
    return out


# ---------------------------------------------------------------------------
# Triple EMA
# ---------------------------------------------------------------------------
@njit(cache=True)
def tema_1d_nb(src, window):
    e1 = ema_1d_nb(src, window)
    e2 = ema_1d_nb(e1, window)
    e3 = ema_1d_nb(e2, window)
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        out[i] = 3.0 * e1[i] - 3.0 * e2[i] + e3[i]
    return out


# ---------------------------------------------------------------------------
# Hull Moving Average
# ---------------------------------------------------------------------------
@njit(cache=True)
def hull_1d_nb(src, window):
    half = max(int(window / 2), 1)
    w1 = wma_1d_nb(src, half)
    w2 = wma_1d_nb(src, window)
    n = src.shape[0]
    diff = np.empty(n, dtype=np.float64)
    for i in range(n):
        diff[i] = 2.0 * _nz(w1[i]) - _nz(w2[i])
    sqrt_w = max(int(round(np.sqrt(window))), 1)
    return wma_1d_nb(diff, sqrt_w)


# ---------------------------------------------------------------------------
# ALMA (Arnaud Legoux)
# ---------------------------------------------------------------------------
@njit(cache=True)
def alma_1d_nb(src, window, offset=0.85, sigma=6.0):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    m = offset * (window - 1)
    s = window / sigma
    weights = np.empty(window, dtype=np.float64)
    w_sum = 0.0
    for j in range(window):
        weights[j] = np.exp(-((j - m) ** 2) / (2.0 * s * s))
        w_sum += weights[j]
    for j in range(window):
        weights[j] /= w_sum
    for i in range(n):
        if i < window - 1:
            out[i] = np.nan
        else:
            s_val = 0.0
            for j in range(window):
                s_val += weights[j] * src[i - window + 1 + j]
            out[i] = s_val
    return out


# ---------------------------------------------------------------------------
# Jurik Moving Average
# ---------------------------------------------------------------------------
@njit(cache=True)
def jurik_1d_nb(src, window, phase=0.0, power=2.0):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    if phase < -100:
        phase_ratio = 0.5
    elif phase > 100:
        phase_ratio = 2.5
    else:
        phase_ratio = phase / 100.0 + 1.5

    beta = 0.45 * (window - 1) / (0.45 * (window - 1) + 2.0)
    alpha = beta ** power

    e0 = 0.0
    e1 = 0.0
    e2 = 0.0
    jma = 0.0

    for i in range(n):
        if i == 0:
            e0 = src[i]
            e1 = 0.0
            e2 = 0.0
            jma = src[i]
        else:
            e0 = (1.0 - alpha) * src[i] + alpha * e0
            e1 = (src[i] - e0) * (1.0 - beta) + beta * e1
            e2 = (e0 + phase_ratio * e1 - jma) * ((1.0 - alpha) ** 2) + (alpha ** 2) * e2
            jma = e2 + jma
        out[i] = jma
    return out


# ---------------------------------------------------------------------------
# Kaufman Adaptive MA (KAMA)
# ---------------------------------------------------------------------------
@njit(cache=True)
def kama_1d_nb(src, window, fast_end=0.666, slow_end=0.0645):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    out[0] = src[0]
    for i in range(1, n):
        direction = abs(src[i] - src[max(0, i - window)])
        noise = 0.0
        for j in range(min(i, window)):
            noise += abs(src[i - j] - src[i - j - 1]) if (i - j - 1) >= 0 else 0.0
        if noise != 0.0:
            er = direction / noise
        else:
            er = 1.0
        sc = (er * (fast_end - slow_end) + slow_end) ** 2
        out[i] = out[i - 1] + sc * (src[i] - out[i - 1])
    return out


# ---------------------------------------------------------------------------
# Fractal Adaptive MA (FRAMA) — simplified (no high/low dependency)
# ---------------------------------------------------------------------------
@njit(cache=True)
def frama_1d_nb(src, window):
    """FRAMA using src only (not high/low). Uses range of src as proxy."""
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    half = max(int(window / 2), 1)
    for i in range(n):
        if i < 2 * window - 1:
            out[i] = src[i]
        else:
            # Full window range
            hi_full = src[i]
            lo_full = src[i]
            for j in range(window):
                v = src[i - j]
                if v > hi_full:
                    hi_full = v
                if v < lo_full:
                    lo_full = v
            n3 = (hi_full - lo_full) / window if window > 0 else 0.0

            # First half
            hi_h1 = src[i]
            lo_h1 = src[i]
            for j in range(half):
                v = src[i - j]
                if v > hi_h1:
                    hi_h1 = v
                if v < lo_h1:
                    lo_h1 = v
            n2 = (hi_h1 - lo_h1) / half if half > 0 else 0.0

            # Second half
            hi_h2 = src[i - half]
            lo_h2 = src[i - half]
            for j in range(half):
                idx = i - half - j
                if idx >= 0:
                    v = src[idx]
                    if v > hi_h2:
                        hi_h2 = v
                    if v < lo_h2:
                        lo_h2 = v
            n1 = (hi_h2 - lo_h2) / half if half > 0 else 0.0

            if n1 > 0 and n2 > 0 and n3 > 0:
                dim = (np.log(n1 + n2) - np.log(n3)) / np.log(2.0)
            else:
                dim = 0.0
            alpha_l = np.exp(-4.6 * (dim - 1.0))
            alpha_l = max(0.01, min(1.0, alpha_l))
            out[i] = src[i] * alpha_l + out[i - 1] * (1.0 - alpha_l)
    return out


# ---------------------------------------------------------------------------
# Volatility Adjusted MA (VAMA)
# ---------------------------------------------------------------------------
@njit(cache=True)
def vama_1d_nb(src, window, volatility_lookback=10):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    mid = ema_1d_nb(src, window)
    for i in range(n):
        dev = src[i] - mid[i]
        vol_up = dev
        vol_down = dev
        for j in range(1, min(i + 1, volatility_lookback)):
            d = src[i - j] - mid[i - j]
            if d > vol_up:
                vol_up = d
            if d < vol_down:
                vol_down = d
        out[i] = mid[i] + (vol_up + vol_down) / 2.0
    return out


# ---------------------------------------------------------------------------
# T3 Tilson
# ---------------------------------------------------------------------------
@njit(cache=True)
def t3_1d_nb(src, window, b=0.7):
    e1 = ema_1d_nb(src, window)
    e2 = ema_1d_nb(e1, window)
    e3 = ema_1d_nb(e2, window)
    e4 = ema_1d_nb(e3, window)
    e5 = ema_1d_nb(e4, window)
    e6 = ema_1d_nb(e5, window)
    c1 = -(b ** 3)
    c2 = 3 * b * b + 3 * b * b * b
    c3 = -6 * b * b - 3 * b - 3 * b * b * b
    c4 = 1 + 3 * b + b * b * b + 3 * b * b
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        out[i] = c1 * e6[i] + c2 * e5[i] + c3 * e4[i] + c4 * e3[i]
    return out


# ---------------------------------------------------------------------------
# T3 Early version (IE2) — linear regression based
# ---------------------------------------------------------------------------
@njit(cache=True)
def t3_early_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        length = min(i + 1, window)
        if length < 2:
            out[i] = src[i]
            continue
        sumx = 0.0
        sumxx = 0.0
        sumxy = 0.0
        sumy = 0.0
        for k in range(length):
            idx = i - k
            price = src[idx] if idx >= 0 else 0.0
            sumx += k
            sumxx += k * k
            sumxy += k * price
            sumy += price
        denom = sumx * sumx - length * sumxx
        if denom != 0.0:
            slope = (length * sumxy - sumx * sumy) / denom
        else:
            slope = 0.0
        average = sumy / length
        out[i] = ((average + slope) + (sumy + slope * sumx) / length) / 2.0
    return out


# ---------------------------------------------------------------------------
# Zero-Lag EMA
# ---------------------------------------------------------------------------
@njit(cache=True)
def zlema_1d_nb(src, window):
    n = src.shape[0]
    lag = int((window - 1) / 2)
    data = np.empty(n, dtype=np.float64)
    for i in range(n):
        lagged = src[i - lag] if i >= lag else src[0]
        data[i] = src[i] + (src[i] - lagged)
    return ema_1d_nb(data, window)


# ---------------------------------------------------------------------------
# McGinley Dynamic
# ---------------------------------------------------------------------------
@njit(cache=True)
def mcginley_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    out[0] = src[0]
    for i in range(1, n):
        prev = out[i - 1]
        if prev == 0.0:
            out[i] = src[i]
        else:
            ratio = src[i] / prev
            out[i] = prev + (src[i] - prev) / (window * (ratio ** 4))
    return out


# ---------------------------------------------------------------------------
# Modular Filter
# ---------------------------------------------------------------------------
@njit(cache=True)
def modular_filter_1d_nb(src, window, beta=0.8, feedback=True, z=0.5):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    alpha = 2.0 / (window + 1.0)
    ts = 0.0
    b_val = 0.0
    c_val = 0.0
    os_val = 0.0
    for i in range(n):
        if feedback:
            a = z * src[i] + (1.0 - z) * ts
        else:
            a = src[i]
        threshold_b = alpha * a + (1.0 - alpha) * b_val
        threshold_c = alpha * a + (1.0 - alpha) * c_val
        b_val = a if a > threshold_b else threshold_b
        c_val = a if a < threshold_c else threshold_c
        if a == b_val:
            os_val = 1.0
        elif a == c_val:
            os_val = 0.0
        upper = beta * b_val + (1.0 - beta) * c_val
        lower = beta * c_val + (1.0 - beta) * b_val
        ts = os_val * upper + (1.0 - os_val) * lower
        out[i] = ts
    return out


# ---------------------------------------------------------------------------
# Coefficient of Variation Weighted MA
# ---------------------------------------------------------------------------
@njit(cache=True)
def covwma_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        if i < window - 1:
            out[i] = np.nan
        else:
            # compute mean and stdev
            mean = 0.0
            for j in range(window):
                mean += src[i - j]
            mean /= window

            sum_cw = 0.0
            sum_c = 0.0
            for j in range(window):
                idx = i - j
                m = 0.0
                for k in range(window):
                    m += src[idx - k] if (idx - k) >= 0 else src[0]
                m /= window
                v = 0.0
                for k in range(window):
                    val = src[idx - k] if (idx - k) >= 0 else src[0]
                    v += (val - m) ** 2
                sd = np.sqrt(v / window)
                c = sd / m if m != 0.0 else 0.0
                sum_cw += src[idx] * c
                sum_c += c
            out[i] = sum_cw / sum_c if sum_c != 0.0 else src[i]
    return out


# ---------------------------------------------------------------------------
# Ehlers 2-pole Super Smoother
# ---------------------------------------------------------------------------
@njit(cache=True)
def ehlers_ssf_2pole_1d_nb(src, length):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    PI = np.pi
    arg = np.sqrt(2.0) * PI / length
    a1 = np.exp(-arg)
    b1 = 2.0 * a1 * np.cos(arg)
    c2 = b1
    c3 = -(a1 ** 2)
    c1 = 1.0 - c2 - c3
    out[0] = src[0]
    if n > 1:
        out[1] = c1 * src[1] + c2 * out[0] + c3 * out[0]
    for i in range(2, n):
        out[i] = c1 * src[i] + c2 * out[i - 1] + c3 * out[i - 2]
    return out


# ---------------------------------------------------------------------------
# Ehlers 3-pole Super Smoother
# ---------------------------------------------------------------------------
@njit(cache=True)
def ehlers_ssf_3pole_1d_nb(src, length):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    PI = np.pi
    arg = PI / length
    a1 = np.exp(-arg)
    b1 = 2.0 * a1 * np.cos(1.738 * arg)
    c1_pole = a1 ** 2
    coef2 = b1 + c1_pole
    coef3 = -(c1_pole + b1 * c1_pole)
    coef4 = c1_pole ** 2
    coef1 = 1.0 - coef2 - coef3 - coef4
    for i in range(n):
        if i < 3:
            out[i] = src[i]
        else:
            out[i] = coef1 * src[i] + coef2 * out[i - 1] + coef3 * out[i - 2] + coef4 * out[i - 3]
    return out


# ---------------------------------------------------------------------------
# Ehlers Super Smoother (2-pole by default, as in Pine source)
# ---------------------------------------------------------------------------
@njit(cache=True)
def ehlers_super_smoother_1d_nb(src, length):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    PI = np.pi
    a1 = np.exp(-PI * np.sqrt(2.0) / length)
    coeff2 = 2.0 * a1 * np.cos(np.sqrt(2.0) * PI / length)
    coeff3 = -(a1 ** 2)
    coeff1 = (1.0 - coeff2 - coeff3) / 2.0
    out[0] = src[0]
    if n > 1:
        out[1] = coeff1 * (src[1] + src[0]) + coeff2 * out[0] + coeff3 * out[0]
    for i in range(2, n):
        out[i] = coeff1 * (src[i] + src[i - 1]) + coeff2 * out[i - 1] + coeff3 * out[i - 2]
    return out


# ---------------------------------------------------------------------------
# EDSMA (Ehlers Dynamic Smoothed MA)
# ---------------------------------------------------------------------------
@njit(cache=True)
def edsma_1d_nb(src, window, ssf_length=20, ssf_poles=2):
    n = src.shape[0]
    # compute zeros
    zeros = np.empty(n, dtype=np.float64)
    zeros[0] = 0.0
    zeros[1] = 0.0 if n > 1 else 0.0
    for i in range(2, n):
        zeros[i] = src[i] - src[i - 2]
    avg_zeros = np.empty(n, dtype=np.float64)
    avg_zeros[0] = zeros[0]
    for i in range(1, n):
        avg_zeros[i] = (zeros[i] + zeros[i - 1]) / 2.0

    if ssf_poles == 3:
        ssf = ehlers_ssf_3pole_1d_nb(avg_zeros, ssf_length)
    else:
        ssf = ehlers_ssf_2pole_1d_nb(avg_zeros, ssf_length)

    # rolling stdev of ssf
    out = np.empty(n, dtype=np.float64)
    edsma_val = src[0]
    for i in range(n):
        # stdev of ssf over window
        length = min(i + 1, window)
        mean = 0.0
        for j in range(length):
            mean += ssf[i - j]
        mean /= length
        var = 0.0
        for j in range(length):
            var += (ssf[i - j] - mean) ** 2
        stdev = np.sqrt(var / length)
        scaled = ssf[i] / stdev if stdev != 0.0 else 0.0
        alpha_e = 5.0 * abs(scaled) / window
        alpha_e = min(alpha_e, 1.0)
        edsma_val = alpha_e * src[i] + (1.0 - alpha_e) * edsma_val
        out[i] = edsma_val
    return out


# ---------------------------------------------------------------------------
# Ehlers EMA Smoother = Ehlers Super Smoother of XEMA
# ---------------------------------------------------------------------------
@njit(cache=True)
def ehlers_ema_smoother_1d_nb(src, smooth_k, smooth_p=3):
    xema_out = xema_1d_nb(src, smooth_k)
    return ehlers_super_smoother_1d_nb(xema_out, smooth_p)


# ---------------------------------------------------------------------------
# Ahrens Moving Average
# ---------------------------------------------------------------------------
@njit(cache=True)
def ahrens_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    out[0] = src[0]
    for i in range(1, n):
        prev = out[i - 1]
        lagged = out[i - window] if i >= window else out[0]
        med_ma = (prev + lagged) / 2.0
        out[i] = prev + (src[i] - med_ma) / window
    return out


# ---------------------------------------------------------------------------
# Alexander Moving Average
# ---------------------------------------------------------------------------
@njit(cache=True)
def alexander_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        if window < 4:
            out[i] = src[i]
            continue
        sumw = window - 2
        s = sumw * src[i]
        for k in range(1, min(i + 1, window + 1)):
            weight = window - k - 2
            sumw += weight
            idx = i - k
            s += weight * (src[idx] if idx >= 0 else src[0])
        out[i] = s / sumw if sumw != 0.0 else src[i]
    return out


# ---------------------------------------------------------------------------
# ADX VMA (Average Directional Volatility Moving Average)
# ---------------------------------------------------------------------------
@njit(cache=True)
def adxvma_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    pdm = 0.0
    mdm = 0.0
    pdi = 0.0
    mdi = 0.0
    adx_out = 0.0
    val = src[0]

    # Store adx_out history for hi/lo scan
    adx_hist = np.zeros(n, dtype=np.float64)

    for i in range(n):
        if i == 0:
            out[i] = src[i]
            continue

        diff = src[i] - src[i - 1]
        tpdm = diff if diff > 0 else 0.0
        tmdm = -diff if diff <= 0 else 0.0

        pdm = ((window - 1.0) * pdm + tpdm) / window
        mdm = ((window - 1.0) * mdm + tmdm) / window

        true_range = pdm + mdm
        tpdi = pdm / true_range if true_range != 0.0 else 0.0
        tmdi = mdm / true_range if true_range != 0.0 else 0.0

        pdi = ((window - 1.0) * pdi + tpdi) / window
        mdi = ((window - 1.0) * mdi + tmdi) / window

        total = pdi + mdi
        tout = abs(pdi - mdi) / total if total > 0 else adx_out
        adx_out = ((window - 1.0) * adx_out + tout) / window
        adx_hist[i] = adx_out

        # hi/lo over window
        thi = adx_out
        tlo = adx_out
        for j in range(1, min(i + 1, window)):
            v = adx_hist[i - j]
            if v > thi:
                thi = v
            if v < tlo:
                tlo = v

        vi = (adx_out - tlo) / (thi - tlo) if (thi - tlo) > 0 else 0.0
        val = ((window - vi) * val + vi * src[i]) / window
        out[i] = val
    return out


# ---------------------------------------------------------------------------
# Integral of Linear Regression Slope (ILRS)
# ---------------------------------------------------------------------------
@njit(cache=True)
def ilrs_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    sma_vals = sma_1d_nb(src, window)
    for i in range(n):
        length = min(i + 1, window)
        if length < 2:
            out[i] = src[i]
            continue
        sum1 = 0.0
        sumy = 0.0
        for j in range(length):
            idx = i - j
            sum1 += j * src[idx]
            sumy += src[idx]
        si = length * (length - 1) * 0.5
        s2 = (length - 1) * length * (2 * length - 1) / 6.0
        num1 = length * sum1 - si * sumy
        num2 = si * si - length * s2
        slope = num1 / num2 if num2 != 0.0 else 0.0
        out[i] = slope + _nz(sma_vals[i], src[i])
    return out


# ---------------------------------------------------------------------------
# Leader EMA
# ---------------------------------------------------------------------------
@njit(cache=True)
def leader_ema_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    alpha = 2.0 / (window + 1.0)
    ldr = 0.0
    ldr2 = 0.0
    for i in range(n):
        ldr = ldr + alpha * (src[i] - ldr)
        ldr2 = ldr2 + alpha * (src[i] - ldr - ldr2)
        out[i] = ldr + ldr2
    return out


# ---------------------------------------------------------------------------
# Recursive Moving Trendline
# ---------------------------------------------------------------------------
@njit(cache=True)
def rmta_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    alpha = 2.0 / (window + 1.0)
    b = src[0]
    rmta_val = src[0]
    for i in range(n):
        prev_b = b
        b = (1.0 - alpha) * b + src[i]
        rmta_val = (1.0 - alpha) * rmta_val + alpha * (src[i] + b - prev_b)
        out[i] = rmta_val
    return out


# ---------------------------------------------------------------------------
# Simple Decycler
# ---------------------------------------------------------------------------
@njit(cache=True)
def decycler_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    PI = np.pi
    alpha_arg = 2.0 * PI / (window * np.sqrt(2.0))
    cos_val = np.cos(alpha_arg)
    alpha = (cos_val + np.sin(alpha_arg) - 1.0) / cos_val if cos_val != 0.0 else 0.0
    hp = 0.0
    hp_1 = 0.0
    hp_2 = 0.0
    for i in range(n):
        s0 = src[i]
        s1 = src[i - 1] if i >= 1 else src[0]
        s2 = src[i - 2] if i >= 2 else src[0]
        hp = ((1.0 - alpha / 2.0) ** 2) * (s0 - 2.0 * s1 + s2) + 2.0 * (1.0 - alpha) * hp_1 - ((1.0 - alpha) ** 2) * hp_2
        hp_2 = hp_1
        hp_1 = hp
        out[i] = src[i] - hp
    return out


# ---------------------------------------------------------------------------
# Triangular MA
# ---------------------------------------------------------------------------
@njit(cache=True)
def triangular_1d_nb(src, window):
    w1 = int(np.ceil(window / 2.0))
    w2 = int(np.floor(window / 2.0)) + 1
    s1 = sma_1d_nb(src, max(w1, 1))
    return sma_1d_nb(s1, max(w2, 1))


# ---------------------------------------------------------------------------
# Optimized EMA (XEMA) — same formula as EMA but explicit mult
# ---------------------------------------------------------------------------
@njit(cache=True)
def xema_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    mult = 2.0 / (window + 1.0)
    out[0] = src[0]
    for i in range(1, n):
        out[i] = mult * src[i] + (1.0 - mult) * out[i - 1]
    return out


# ---------------------------------------------------------------------------
# Donchian
# ---------------------------------------------------------------------------
@njit(cache=True)
def donchian_1d_nb(src, window):
    """Mid-line of Donchian channel (avg of highest/lowest over window)."""
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        hi = src[i]
        lo = src[i]
        for j in range(1, min(i + 1, window)):
            v = src[i - j]
            if v > hi:
                hi = v
            if v < lo:
                lo = v
        out[i] = (hi + lo) / 2.0
    return out


# ---------------------------------------------------------------------------
# Donchian V2
# ---------------------------------------------------------------------------
@njit(cache=True)
def donchian_v2_1d_nb(src, window, kidiv=2):
    """Donchian V2 from Pine Script: (kijun + conversionLine) / 2."""
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    half = max(int(window / kidiv), 1)
    for i in range(n):
        hi = src[i]
        lo = src[i]
        for j in range(1, min(i + 1, window)):
            v = src[i - j]
            if v > hi:
                hi = v
            if v < lo:
                lo = v
        kijun = (hi + lo) / 2.0

        hi2 = src[i]
        lo2 = src[i]
        for j in range(1, min(i + 1, half)):
            v = src[i - j]
            if v > hi2:
                hi2 = v
            if v < lo2:
                lo2 = v
        conv = (hi2 + lo2) / 2.0
        out[i] = (kijun + conv) / 2.0
    return out


# ---------------------------------------------------------------------------
# Linear Regression (LSMA / linreg with offset=0)
# ---------------------------------------------------------------------------
@njit(cache=True)
def linreg_1d_nb(src, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        length = min(i + 1, window)
        if length < 2:
            out[i] = src[i]
            continue
        sumx = 0.0
        sumy = 0.0
        sumxx = 0.0
        sumxy = 0.0
        for j in range(length):
            x = float(j)
            y = src[i - length + 1 + j]
            sumx += x
            sumy += y
            sumxx += x * x
            sumxy += x * y
        denom = length * sumxx - sumx * sumx
        if denom != 0.0:
            slope = (length * sumxy - sumx * sumy) / denom
            intercept = (sumy - slope * sumx) / length
            out[i] = intercept + slope * (length - 1)
        else:
            out[i] = sumy / length
    return out


# ---------------------------------------------------------------------------
# VWMA stub — requires volume, handled separately in the factory
# ---------------------------------------------------------------------------
@njit(cache=True)
def vwma_1d_nb(src, volume, window):
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        if i < window - 1:
            out[i] = np.nan
        else:
            sv = 0.0
            tv = 0.0
            for j in range(window):
                sv += src[i - j] * volume[i - j]
                tv += volume[i - j]
            out[i] = sv / tv if tv != 0.0 else src[i]
    return out


# ---------------------------------------------------------------------------
# Universal dispatcher (no volume)
# ---------------------------------------------------------------------------
@njit(cache=True)
def universal_ma_1d_nb(src, window, ma_type, phase=0.0, power=2.0):
    """Compute any MA type on a 1-D array.

    Parameters
    ----------
    src : 1-D float array
    window : int
    ma_type : int (one of the MA_* constants)
    phase : float (Jurik phase parameter)
    power : float (Jurik power parameter)
    """
    if ma_type == MA_SMA:
        return sma_1d_nb(src, window)
    elif ma_type == MA_EMA:
        return ema_1d_nb(src, window)
    elif ma_type == MA_WMA:
        return wma_1d_nb(src, window)
    elif ma_type == MA_RMA:
        return rma_1d_nb(src, window)
    elif ma_type == MA_DEMA:
        return dema_1d_nb(src, window)
    elif ma_type == MA_TEMA:
        return tema_1d_nb(src, window)
    elif ma_type == MA_HULL:
        return hull_1d_nb(src, window)
    elif ma_type == MA_ALMA:
        return alma_1d_nb(src, window)
    elif ma_type == MA_JURIK:
        return jurik_1d_nb(src, window, phase, power)
    elif ma_type == MA_KAMA:
        return kama_1d_nb(src, window)
    elif ma_type == MA_FRAMA:
        return frama_1d_nb(src, window)
    elif ma_type == MA_VAMA:
        return vama_1d_nb(src, window)
    elif ma_type == MA_T3:
        return t3_1d_nb(src, window)
    elif ma_type == MA_T3_EARLY:
        return t3_early_1d_nb(src, window)
    elif ma_type == MA_ZLEMA:
        return zlema_1d_nb(src, window)
    elif ma_type == MA_MCGINLEY:
        return mcginley_1d_nb(src, window)
    elif ma_type == MA_MODULAR_FILTER:
        return modular_filter_1d_nb(src, window)
    elif ma_type == MA_COVWMA:
        return covwma_1d_nb(src, window)
    elif ma_type == MA_EDSMA:
        return edsma_1d_nb(src, window)
    elif ma_type == MA_EHLERS_SUPER_SMOOTHER:
        return ehlers_super_smoother_1d_nb(src, window)
    elif ma_type == MA_EHLERS_EMA_SMOOTHER:
        return ehlers_ema_smoother_1d_nb(src, window)
    elif ma_type == MA_AHRENS:
        return ahrens_1d_nb(src, window)
    elif ma_type == MA_ALEXANDER:
        return alexander_1d_nb(src, window)
    elif ma_type == MA_ADXVMA:
        return adxvma_1d_nb(src, window)
    elif ma_type == MA_ILRS:
        return ilrs_1d_nb(src, window)
    elif ma_type == MA_LEADER_EMA:
        return leader_ema_1d_nb(src, window)
    elif ma_type == MA_RMTA:
        return rmta_1d_nb(src, window)
    elif ma_type == MA_DECYCLER:
        return decycler_1d_nb(src, window)
    elif ma_type == MA_TRIANGULAR:
        return triangular_1d_nb(src, window)
    elif ma_type == MA_XEMA:
        return xema_1d_nb(src, window)
    elif ma_type == MA_DONCHIAN:
        return donchian_1d_nb(src, window)
    elif ma_type == MA_DONCHIAN_V2:
        return donchian_v2_1d_nb(src, window)
    elif ma_type == MA_LINREG:
        return linreg_1d_nb(src, window)
    else:
        return sma_1d_nb(src, window)


# ---------------------------------------------------------------------------
# 2-D wrapper (for IndicatorFactory apply_func)
# ---------------------------------------------------------------------------
@njit(cache=True)
def universal_ma_nb(close, window, ma_type, phase=0.0, power=2.0):
    """2-D wrapper: apply universal_ma_1d_nb to each column."""
    nrows = close.shape[0]
    ncols = close.shape[1]
    out = np.empty((nrows, ncols), dtype=np.float64)
    for col in range(ncols):
        out[:, col] = universal_ma_1d_nb(
            close[:, col],
            window,
            ma_type,
            phase,
            power,
        )
    return out
