"""Celestial Channel Lines — convert planetary longitude to price levels.

Ports CelestialChannelLines.txt from Pine Script. Creates a grid of
support/resistance lines from planetary ecliptic longitudes.

Usage
-----
>>> from src.indicators.celestial_channels import celestial_channel_levels
>>> levels = celestial_channel_levels(timestamps_ms, pnum=2, scaler=16.18, base=6, n_harmonics=10)
>>> # levels is a DataFrame with columns "h0" through "h9"
"""

import numpy as np
import pandas as pd

from src.indicators.astro_lib import planet_longitude_series, midpoint
from src.indicators.nb.astro_nb import jdn_v2, j2k, ecliptic_longitude, midpoint as nb_midpoint


def celestial_channel_levels(
    timestamps_ms,
    pnum=2,
    scaler=16.18,
    base=6,
    n_harmonics=10,
    mirror=False,
    pnum_b=None,
):
    """Compute celestial channel price levels for each bar.

    Parameters
    ----------
    timestamps_ms : array-like of int
        Unix timestamps in milliseconds for each bar.
    pnum : int
        Planet number (see astro_lib.PLANET_NUMBERS).
    scaler : float
        Dollars per degree (1 degree = $scaler).
    base : int
        Base harmonic offset (multiples of 360 * scaler).
    n_harmonics : int
        Number of harmonic levels to generate (0..n_harmonics-1).
    mirror : bool
        If True, negate the longitude before scaling.
    pnum_b : int or None
        If set, compute midpoint with this second planet.

    Returns
    -------
    pd.DataFrame
        Columns "h0", "h1", ..., "h{n-1}" with price levels per bar.
        Index is integer range (caller should set index to match their data).
    """
    ts = np.asarray(timestamps_ms, dtype=np.float64)
    n = len(ts)
    mirror_mult = -1.0 if mirror else 1.0

    longitudes = np.empty(n, dtype=np.float64)
    for i in range(n):
        jd = jdn_v2(ts[i], True)
        d = j2k(jd)
        lon_a = ecliptic_longitude(d, pnum)
        if pnum_b is not None:
            lon_b = ecliptic_longitude(d, pnum_b)
            longitudes[i] = nb_midpoint(lon_a, lon_b)
        else:
            longitudes[i] = lon_a

    levels = {}
    for h in range(n_harmonics):
        col = np.empty(n, dtype=np.float64)
        for i in range(n):
            col[i] = (mirror_mult * longitudes[i] * scaler) + (scaler * 360.0 * h) + (scaler * 360.0 * base)
        levels[f"h{h}"] = col

    return pd.DataFrame(levels)
