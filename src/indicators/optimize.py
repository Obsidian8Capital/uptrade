"""Parameter optimization via VBT's built-in grid search.

Usage
-----
>>> from src.indicators.optimize import optimize_sniper, optimize_vzo
>>> results = optimize_sniper(close, high, low, volume)
>>> print(results.sort_values("sharpe_ratio", ascending=False).head())
"""

import itertools

import numpy as np
import pandas as pd
import vectorbtpro as vbt

from src.indicators.sniper import SniperProX
from src.indicators.vzo import VZOProX
from src.indicators.nb.ma_library_nb import MA_JURIK, MA_HULL, MA_KAMA, MA_EMA, MA_T3


def optimize_sniper(
    close,
    high,
    low,
    volume,
    lengths=None,
    ma_types=None,
    ob_os_values=None,
    init_cash=100_000,
    fees=0.001,
):
    """Grid search over SniperProX parameters.

    Parameters
    ----------
    lengths : list of int
    ma_types : list of int (MA type codes)
    ob_os_values : list of float

    Returns
    -------
    pd.DataFrame with columns: length, ma_type, ob_os, sharpe_ratio, total_return, max_dd, n_trades
    """
    if lengths is None:
        lengths = [14, 21, 28, 34]
    if ma_types is None:
        ma_types = [MA_JURIK, MA_HULL, MA_KAMA]
    if ob_os_values is None:
        ob_os_values = [1.0, 1.386, 1.5]

    results = []
    for length, mt, obs in itertools.product(lengths, ma_types, ob_os_values):
        try:
            sniper = SniperProX.run(
                close, high, low, volume,
                length=length, ma_type=mt,
                overbought_oversold=obs,
            )
            entries = ~np.isnan(np.asarray(sniper.major_buy, dtype=np.float64))
            exits = ~np.isnan(np.asarray(sniper.major_sell, dtype=np.float64))

            if not np.any(entries):
                continue

            pf = vbt.Portfolio.from_signals(
                close=close, entries=entries, exits=exits,
                init_cash=init_cash, fees=fees,
            )
            stats = pf.stats()
            results.append({
                "length": length,
                "ma_type": mt,
                "ob_os": obs,
                "sharpe_ratio": stats.get("Sharpe Ratio", np.nan),
                "total_return": stats.get("Total Return [%]", np.nan),
                "max_dd": stats.get("Max Drawdown [%]", np.nan),
                "n_trades": stats.get("Total Trades", 0),
            })
        except Exception:
            continue

    return pd.DataFrame(results)


def optimize_vzo(
    close,
    volume,
    lengths=None,
    ma_types=None,
    init_cash=100_000,
    fees=0.001,
):
    """Grid search over VZO parameters.

    Returns
    -------
    pd.DataFrame
    """
    if lengths is None:
        lengths = [10, 14, 21, 28]
    if ma_types is None:
        ma_types = [MA_JURIK, MA_EMA, MA_T3]

    results = []
    for length, mt in itertools.product(lengths, ma_types):
        try:
            vzo = VZOProX.run(close, volume, vzo_length=length, ma_type=mt)
            entries = ~np.isnan(np.asarray(vzo.major_buy, dtype=np.float64))
            exits = ~np.isnan(np.asarray(vzo.major_sell, dtype=np.float64))

            if not np.any(entries):
                continue

            pf = vbt.Portfolio.from_signals(
                close=close, entries=entries, exits=exits,
                init_cash=init_cash, fees=fees,
            )
            stats = pf.stats()
            results.append({
                "vzo_length": length,
                "ma_type": mt,
                "sharpe_ratio": stats.get("Sharpe Ratio", np.nan),
                "total_return": stats.get("Total Return [%]", np.nan),
                "max_dd": stats.get("Max Drawdown [%]", np.nan),
                "n_trades": stats.get("Total Trades", 0),
            })
        except Exception:
            continue

    return pd.DataFrame(results)
