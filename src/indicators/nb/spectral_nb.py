"""Numba kernels for Spectral Analysis Oscillator (Hurst + Goertzel)."""

import numpy as np
from numba import njit


@njit(cache=True)
def bandpass_1d_nb(src, period, bandwidth):
    """Hurst Bandpass Filter (IIR, 2nd order)."""
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    PI = np.pi
    beta = np.cos(PI * (360.0 / period) / 180.0)
    gamma = 1.0 / np.cos(PI * (720.0 * bandwidth / period) / 180.0)
    alpha = gamma - np.sqrt(gamma * gamma - 1.0)
    out[0] = 0.0
    out[1] = 0.0 if n > 1 else 0.0
    for i in range(2, n):
        out[i] = 0.5 * (1.0 - alpha) * (src[i] - src[i - 2]) + beta * (1.0 + alpha) * out[i - 1] - alpha * out[i - 2]
    return out


@njit(cache=True)
def goertzel_1d_nb(src, window_size, cycle_len, scale_factor=100000.0):
    """Generalized Goertzel DFT at a specific cycle frequency.

    Returns an oscillating series: amplitude * sin(2*pi*bar_index / cycle_len).
    """
    n = src.shape[0]
    out = np.empty(n, dtype=np.float64)
    PI = np.pi

    for i in range(n):
        length = min(i + 1, window_size)
        if length < 2:
            out[i] = 0.0
            continue

        k = length / cycle_len
        omega = 2.0 * PI * k / length
        sine = np.sin(omega)
        cosine = np.cos(omega)
        coeff = 2.0 * cosine

        q0 = 0.0
        q1 = 0.0
        q2 = 0.0

        for j in range(length):
            val = src[i - length + 1 + j]
            q0 = coeff * q1 - q2 + val
            q2 = q1
            q1 = q0

        real = (cosine * q1 - q2) / length * 2.0
        imag = (sine * q1) / length * 2.0

        # stdev of source over window for normalization
        mean = 0.0
        for j in range(length):
            mean += src[i - j]
        mean /= length
        var = 0.0
        for j in range(length):
            var += (src[i - j] - mean) ** 2
        normalizer = np.sqrt(var / length)

        amp = np.sqrt(real * real + imag * imag) * normalizer
        final_amp = amp / scale_factor
        out[i] = final_amp * np.sin(PI * 2.0 * i / cycle_len)
    return out


@njit(cache=True)
def spectral_analysis_1d_nb(
    src,
    periods,
    composite_mask,
    bandwidth,
    method,
    window_size,
    scale_factor,
):
    """Compute all cycle bandpass filters and composite.

    Parameters
    ----------
    src : 1-D array
    periods : 1-D array of floats (11 cycle periods)
    composite_mask : 1-D array of bools (which cycles to include in composite)
    bandwidth : float
    method : int (0 = Hurst, 1 = Goertzel)
    window_size : int
    scale_factor : float

    Returns
    -------
    cycles : 2-D array (n, 11) — individual cycle values
    composite : 1-D array — sum of enabled cycles
    """
    n = src.shape[0]
    n_cycles = periods.shape[0]
    cycles = np.empty((n, n_cycles), dtype=np.float64)

    for c in range(n_cycles):
        if method == 0:
            cycles[:, c] = bandpass_1d_nb(src, periods[c], bandwidth)
        else:
            cycles[:, c] = goertzel_1d_nb(src, window_size, periods[c], scale_factor)

    composite = np.zeros(n, dtype=np.float64)
    for c in range(n_cycles):
        if composite_mask[c]:
            for i in range(n):
                composite[i] += cycles[i, c]

    return cycles, composite
