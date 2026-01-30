"""Numba kernels for AstroLib — astronomical math.

Ports the core math-heavy functions from AstroLib.txt to @njit.
"""

import numpy as np
from numba import njit

TPI = 2.0 * np.pi
PI = np.pi


@njit(cache=True)
def range360(x):
    if x < 0:
        return x - 360.0 * int(np.sign(x / 360.0))
    return x - 360.0 * int(x / 360.0)


@njit(cache=True)
def range2pi(x):
    if x < 0:
        return x - TPI * int(np.sign(x / TPI))
    return x - TPI * int(x / TPI)


@njit(cache=True)
def deg_sin(x):
    return np.sin(np.radians(x))


@njit(cache=True)
def deg_cos(x):
    return np.cos(np.radians(x))


@njit(cache=True)
def deg_tan(x):
    return np.tan(np.radians(x))


@njit(cache=True)
def deg_arcsin(x):
    return np.degrees(np.arcsin(x))


@njit(cache=True)
def deg_arccos(x):
    return np.degrees(np.arccos(x))


@njit(cache=True)
def deg_arctan(x):
    return np.degrees(np.arctan(x))


@njit(cache=True)
def atan2_nb(y, x):
    if x == 0.0:
        if y > 0.0:
            return PI / 2.0
        elif y < 0.0:
            return -PI / 2.0
        else:
            return 0.0
    if x > 0.0:
        return np.arctan(y / x)
    if y >= 0.0:
        return np.arctan(y / x) + PI
    return np.arctan(y / x) - PI


@njit(cache=True)
def deg_atan2(y, x):
    r = np.degrees(atan2_nb(y, x))
    return r + 360.0 if r < 0 else r


@njit(cache=True)
def jdn_v2(t_ms, with_fraction):
    if with_fraction:
        return t_ms / 86400000.0 + 2440587.5
    return np.floor(t_ms / 86400000.0) + 2440587.5


@njit(cache=True)
def j2k(jdn):
    return jdn - 2451545.0


@njit(cache=True)
def obliquity(d):
    T = d / 36525.0
    return 23.43929111 - (46.815 + (0.00059 - 0.001813 * T) * T) * T / 3600.0


@njit(cache=True)
def rectangular(R, theta, phi, index):
    r_cos = R * deg_cos(theta)
    if index == 1:
        return r_cos * deg_cos(phi)
    elif index == 2:
        return r_cos * deg_sin(phi)
    elif index == 3:
        return R * deg_sin(theta)
    return 0.0


@njit(cache=True)
def r_length(x, y, z):
    return np.sqrt(x * x + y * y + z * z)


@njit(cache=True)
def spherical(x, y, z, index):
    rho = x * x + y * y
    rho_sqrt = np.sqrt(rho)
    if index == 1:
        return np.sqrt(rho + z * z)
    elif index == 2:
        return deg_arctan(z / rho_sqrt) if rho_sqrt != 0 else 0.0
    elif index == 3:
        return deg_atan2(y, x) if rho_sqrt != 0 else 0.0
    return 0.0


@njit(cache=True)
def requatorial(x, y, z, d, index):
    obl = obliquity(d)
    if index == 1:
        return x
    elif index == 2:
        return y * deg_cos(obl) - z * deg_sin(obl)
    elif index == 3:
        return y * deg_sin(obl) + z * deg_cos(obl)
    return 0.0


@njit(cache=True)
def recliptic(x, y, z, d, index):
    obl = obliquity(d)
    if index == 1:
        return x
    elif index == 2:
        return y * deg_cos(obl) + z * deg_sin(obl)
    elif index == 3:
        return -y * deg_sin(obl) + z * deg_cos(obl)
    return 0.0


# ---------------------------------------------------------------------------
# Sun position
# ---------------------------------------------------------------------------
@njit(cache=True)
def ssun(d, index):
    """Sun position in ecliptic coordinates.

    index: 1=R, 2=lat(0), 3=ecliptic_longitude, 4=equation_of_time
    """
    T = d / 36525.0
    g = range360(357.5291092 + 35999.05034 * T - 0.0001536 * T * T)
    L = range360(280.46645 + 36000.76983 * T + 0.0003032 * T * T)
    C = (1.914602 * deg_sin(g) - 0.004817 * T * deg_sin(g)
         + 0.019993 * deg_sin(2 * g) - 0.000101 * T * deg_sin(2 * g)
         + 0.000289 * deg_sin(3 * g))
    lam = range360(L + C)
    R = 1.00014 - 0.01671 * deg_cos(g) - 0.00014 * deg_cos(2 * g)
    if index == 1:
        return R
    elif index == 2:
        return 0.0
    elif index == 3:
        return lam
    elif index == 4:
        return (-1.915 * deg_sin(g) - 0.02 * deg_sin(2 * g)
                + 2.466 * deg_sin(2 * lam) - 0.053 * deg_sin(4 * lam))
    return 0.0


# ---------------------------------------------------------------------------
# Moon position (simplified Brown's lunar theory)
# ---------------------------------------------------------------------------
@njit(cache=True)
def smoon(dx, index):
    """Moon position. index: 1=distance, 2=latitude, 3=longitude."""
    d = dx + 1.5
    T = d / 36525.0
    Nm = np.radians(range360(125.1228 - 0.0529538083 * d))
    im = np.radians(5.1454)
    wm = np.radians(range360(318.0634 + 0.1643573223 * d))
    am = 60.2666 * (1.0 - 0.000002 * T)
    ecm = 0.0549 + 0.00000002 * T
    Mm = np.radians(range360(115.3654 + 13.0649929509 * d))

    # Kepler equation (simple iteration)
    em = Mm + ecm * np.sin(Mm) * (1.0 + ecm * np.cos(Mm))
    xv = am * (np.cos(em) - ecm)
    yv = am * np.sqrt(1.0 - ecm * ecm) * np.sin(em)
    vm = atan2_nb(yv, xv)
    rm = np.sqrt(xv * xv + yv * yv)

    ws = np.radians(range360(282.9404 + 0.0000470935 * d))
    Ms = np.radians(range360(356.047 + 0.9856002585 * d))
    ls = Ms + ws
    lm = Mm + wm + Nm
    dm = lm - ls
    f = lm - Nm

    dlon = (-1.274 * np.sin(Mm - 2 * dm) + 0.658 * np.sin(2 * dm)
            - 0.186 * np.sin(Ms) - 0.114 * np.sin(2 * f)
            - 0.059 * np.sin(2 * Mm - 2 * dm) + 0.054 * np.sin(Mm + 2 * dm)
            + 0.022 * np.sin(Mm - dm))
    dlat = (-0.173 * np.sin(f - 2 * dm) - 0.055 * np.sin(Mm - f - 2 * dm)
            + 0.033 * np.sin(f + 2 * dm) + 0.017 * np.sin(2 * Mm + f))
    drm = -0.58 * np.cos(Mm - 2 * dm) - 0.46 * np.cos(2 * dm)

    lon = range360(np.degrees(atan2_nb(yv, xv))) + dlon
    lat = np.degrees(np.arctan(rm * np.sin(vm + wm) * np.sin(im) / np.sqrt(xv * xv + yv * yv))) + dlat
    rm = rm + drm

    if index == 1:
        return rm
    elif index == 2:
        return lat
    elif index == 3:
        return lon
    return 0.0


# ---------------------------------------------------------------------------
# Kepler equation solver
# ---------------------------------------------------------------------------
@njit(cache=True)
def kepler(M_deg, e):
    """Solve Kepler's equation M = E - e*sin(E). Returns E in degrees."""
    M_rad = np.radians(M_deg)
    E = M_rad
    for _ in range(10):
        delta = E - e * np.sin(E) - M_rad
        if abs(delta) < 1e-6:
            break
        E = E - delta / (1.0 - e * np.cos(E))
    return np.degrees(E)


# ---------------------------------------------------------------------------
# Planet orbital elements (simplified — major planets only)
# ---------------------------------------------------------------------------
@njit(cache=True)
def planet_elements(d, pnum):
    """Return (inclination, Om, w, a, e, M) for planet pnum.

    All angles in radians except M which is in radians (wrapped 0..2pi).
    """
    T = d / 36525.0
    # Default
    i_val = 0.0
    Om = 0.0
    w = 0.0
    a = 0.0
    e = 0.0
    M = 0.0

    if pnum == 0:  # Sun
        M = range2pi(np.radians(ssun(d, 3)))
        a = 1.0
    elif pnum == 2:  # Mercury
        i_val = np.radians(7.00487 - 1.78797e-7 * d)
        Om = np.radians(48.33167 - 3.3942e-6 * d)
        w = np.radians(77.45645 + 4.36208e-6 * d)
        a = 0.38709893 + 1.80698e-11 * d
        e = 0.20563069 + 6.91855e-10 * d
        M = range2pi(np.radians(252.25084 + 4.092338796 * d))
    elif pnum == 3:  # Venus
        i_val = np.radians(3.39471 - 2.17507e-8 * d)
        Om = np.radians(76.68069 - 7.5815e-6 * d)
        w = np.radians(131.53298 - 8.27439e-7 * d)
        a = 0.72333199 + 2.51882e-11 * d
        e = 0.00677323 - 1.35195e-9 * d
        M = range2pi(np.radians(181.97973 + 1.602130474 * d))
    elif pnum == 4:  # Mars
        i_val = np.radians(1.85061 - 1.93703e-7 * d)
        Om = np.radians(49.57854 - 7.7587e-6 * d)
        w = np.radians(336.04084 + 1.187e-5 * d)
        a = 1.52366231 - 1.977e-9 * d
        e = 0.09341233 - 3.25859e-9 * d
        M = range2pi(np.radians(355.45332 + 0.524033035 * d))
    elif pnum == 5:  # Jupiter
        i_val = np.radians(1.3053 - 3.15613e-8 * d)
        Om = np.radians(100.55615 + 9.25675e-6 * d)
        w = np.radians(14.75385 + 6.38779e-6 * d)
        a = 5.20336301 + 1.66289e-8 * d
        e = 0.04839266 - 3.52635e-9 * d
        M = range2pi(np.radians(34.40438 + 0.083086762 * d))
    elif pnum == 6:  # Saturn
        i_val = np.radians(2.48446 + 4.64674e-8 * d)
        Om = np.radians(113.71504 - 1.21e-5 * d)
        w = np.radians(92.43194 - 1.48216e-5 * d)
        a = 9.53707032 - 8.25544e-8 * d
        e = 0.0541506 - 1.00649e-8 * d
        M = range2pi(np.radians(49.94432 + 0.033470629 * d))
    elif pnum == 7:  # Uranus
        i_val = np.radians(0.76986 - 1.58947e-8 * d)
        Om = np.radians(74.22988 + 1.27873e-5 * d)
        w = np.radians(170.96424 + 9.9822e-6 * d)
        a = 19.19126393 + 4.16222e-8 * d
        e = 0.04716771 - 5.24298e-9 * d
        M = range2pi(np.radians(313.23218 + 0.011731294 * d))
    elif pnum == 8:  # Neptune
        i_val = np.radians(1.76917 - 2.76827e-8 * d)
        Om = np.radians(131.72169 - 1.1503e-6 * d)
        w = np.radians(44.97135 - 6.42201e-6 * d)
        a = 30.06896348 - 3.42768e-8 * d
        e = 0.00858587 + 6.88296e-10 * d
        M = range2pi(np.radians(304.88003 + 0.0059810572 * d))
    elif pnum == 9:  # Pluto
        i_val = np.radians(17.14175 + 8.41889e-8 * d)
        Om = np.radians(110.30347 - 2.839e-7 * d)
        w = np.radians(224.06676 - 1.00578e-6 * d)
        a = 39.48168677 - 2.10574e-8 * d
        e = 0.24880766 + 1.77002e-9 * d
        M = range2pi(np.radians(238.92881 + 0.00397557152635181 * d))
    elif pnum == 14:  # Earth
        i_val = np.radians(5e-5 - 3.56985e-7 * d)
        Om = np.radians(-11.26064 - 1.3863e-4 * d)
        w = np.radians(102.94719 + 9.11309e-6 * d)
        a = 1.00000011 - 1.36893e-12 * d
        e = 0.01671022 - 1.04148e-9 * d
        M = range2pi(np.radians(100.46435 + 0.985609101 * d))

    return i_val, Om, w, a, e, M


@njit(cache=True)
def rplanet(d, pnum, index):
    """Heliocentric rectangular coordinates for planet."""
    i_val, Om, w, a, e, M = planet_elements(d, pnum)
    E = kepler(np.degrees(M), e)
    v = 2.0 * deg_arctan(np.sqrt((1.0 + e) / (1.0 - e)) * deg_tan(E / 2.0))
    r = a * (1.0 - e * deg_cos(E))
    Om_deg = np.degrees(Om)
    w_deg = np.degrees(w)
    i_deg = np.degrees(i_val)
    x = r * (deg_cos(Om_deg) * deg_cos(v + w_deg - Om_deg) - deg_sin(Om_deg) * deg_sin(v + w_deg - Om_deg) * deg_cos(i_deg))
    y = r * (deg_sin(Om_deg) * deg_cos(v + w_deg - Om_deg) + deg_cos(Om_deg) * deg_sin(v + w_deg - Om_deg) * deg_cos(i_deg))
    z = r * deg_sin(v + w_deg - Om_deg) * deg_sin(i_deg)
    if index == 1:
        return x
    elif index == 2:
        return y
    elif index == 3:
        return z
    return 0.0


@njit(cache=True)
def ecliptic_longitude(d, pnum):
    """Get geocentric ecliptic longitude for a planet."""
    if pnum == 0:
        return ssun(d, 3)
    elif pnum == 1:
        return smoon(d, 3)
    elif pnum == 14:
        return range360(ssun(d, 3) + 180.0)
    else:
        xp = rplanet(d, pnum, 1)
        yp = rplanet(d, pnum, 2)
        zp = rplanet(d, pnum, 3)
        xe = rplanet(d, 14, 1)
        ye = rplanet(d, 14, 2)
        ze = rplanet(d, 14, 3)
        return spherical(xp - xe, yp - ye, zp - ze, 3)


@njit(cache=True)
def midpoint(deg1, deg2):
    """Midpoint of two ecliptic longitudes."""
    d1 = range360(deg1)
    d2 = range360(deg2)
    diff = abs(d2 - d1)
    if diff > 180.0:
        mid = (d1 + d2 + 360.0) / 2.0
    else:
        mid = (d1 + d2) / 2.0
    return range360(mid)
