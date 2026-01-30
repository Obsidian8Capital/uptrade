"""AstroLib — Python port of the Pine Script AstroLib library.

Provides astronomical calculation functions for financial astrology:
- Julian Date conversions
- Sun, Moon, Planet positions (ecliptic longitude)
- Zodiac sign, Nakshatra classification
- Aspect detection (conjunction, sextile, square, trine, opposition)
- Midpoint calculations

Heavy math is in nb/astro_nb.py (Numba). This module provides the
pure-Python convenience layer (lookup tables, string formatting).
"""

import numpy as np

from src.indicators.nb.astro_nb import (
    jdn_v2,
    j2k,
    range360,
    ssun,
    smoon,
    ecliptic_longitude,
    midpoint,
    kepler,
    rplanet,
)

# Re-export core Numba functions
jdn = jdn_v2
j2k_from_jdn = j2k

# Planet number mapping
PLANET_NUMBERS = {
    "Sun": 0, "Moon": 1, "Mercury": 2, "Venus": 3, "Mars": 4,
    "Jupiter": 5, "Saturn": 6, "Uranus": 7, "Neptune": 8, "Pluto": 9,
    "Mean Node": 10, "True Node": 11, "Mean Apogee": 12,
    "Osculating Apogee": 13, "Earth": 14,
    "Ceres": 17, "Juno": 19, "Vesta": 20,
    "Cupido": 40, "Hades": 41, "Zeus": 42, "Kronos": 43,
    "Apollon": 44, "Admetos": 45, "Vulcanus": 46, "Poseidon": 47,
    "Pallas": 100, "Chiron": 101, "Astraea": 102, "Hebe": 103, "Pholus": 104,
}

PLANET_NAMES = {v: k for k, v in PLANET_NUMBERS.items()}

PLANET_SIGNS = {
    0: "\u2609", 1: "\u263D", 2: "\u263F", 3: "\u2640", 4: "\u2642",
    5: "\u2643", 6: "\u2644", 7: "\u26E2", 8: "\u2646", 9: "\u2647",
}

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

ZODIAC_SYMBOLS = [
    "\u2648", "\u2649", "\u264A", "\u264B", "\u264C", "\u264D",
    "\u264E", "\u264F", "\u2650", "\u2651", "\u2652", "\u2653",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
    "Anuradha", "Jyeshta", "Mula", "Purva Ashadha", "Uttara Ashadha",
    "Shravana", "Dhanistha", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati",
]

ASPECTS = {
    0: "Conjunction", 30: "Semi-Sextile", 60: "Sextile",
    90: "Square", 120: "Trine", 150: "Inconjunct", 180: "Opposition",
}


def get_zodiac(deg):
    """Return (sign_name, degrees_in_sign, minutes) from ecliptic longitude."""
    deg_norm = range360(deg)
    sign_idx = int(deg_norm // 30)
    deg_in_sign = deg_norm % 30
    minutes = (deg_in_sign - int(deg_in_sign)) * 60
    return ZODIAC_SIGNS[sign_idx], int(deg_in_sign), round(minutes, 2)


def get_nakshatra(deg):
    """Return Nakshatra name from ecliptic longitude."""
    deg_norm = range360(deg)
    idx = int(deg_norm / 13.333333333333334)
    idx = min(idx, 26)
    return NAKSHATRAS[idx]


def get_aspect(deg1, deg2, orb=6.0):
    """Identify aspect between two ecliptic longitudes.

    Returns (aspect_name, exact_diff, orb_diff) or None if no aspect within orb.
    """
    d1 = range360(deg1)
    d2 = range360(deg2)
    diff = abs(d1 - d2)
    if diff > 180:
        diff = 360 - diff
    for angle, name in ASPECTS.items():
        if abs(diff - angle) <= orb:
            return name, diff, abs(diff - angle)
    return None


def planet_longitude_series(timestamps_ms, pnum):
    """Compute ecliptic longitude for each timestamp (milliseconds).

    Parameters
    ----------
    timestamps_ms : array-like of int (Unix ms)
    pnum : int (planet number)

    Returns
    -------
    np.ndarray of float64 (ecliptic longitude in degrees)
    """
    ts = np.asarray(timestamps_ms, dtype=np.float64)
    out = np.empty(len(ts), dtype=np.float64)
    for i in range(len(ts)):
        jd = jdn_v2(ts[i], True)
        d = j2k(jd)
        out[i] = ecliptic_longitude(d, pnum)
    return out
