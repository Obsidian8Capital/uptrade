"""Signal generation — combine indicators into entry/exit boolean arrays.

Usage
-----
>>> from src.indicators.signals import generate_signals
>>> entries, exits = generate_signals(close, high, low, volume)
"""

import numpy as np
import pandas as pd


def generate_signals(
    close,
    high,
    low,
    volume,
    # SniperProX params
    sniper_length=28,
    sniper_ma_type="Jurik Moving Average",
    sniper_ob_os=1.386,
    # VZO params
    vzo_length=14,
    vzo_ma_type="Jurik Moving Average",
    vzo_minor_buy=-40.0,
    vzo_minor_sell=40.0,
    # General
    use_sniper=True,
    use_vzo=True,
    combine_mode="and",
):
    """Generate entry/exit boolean arrays from SniperProX and VZO.

    Parameters
    ----------
    close, high, low, volume : pd.Series or np.ndarray
    combine_mode : str
        "and" = both must signal, "or" = either signals.

    Returns
    -------
    entries, exits : pd.Series of bool (or np.ndarray)
    """
    from src.indicators.sniper import SniperProX
    from src.indicators.vzo import VZOProX

    n = len(close)
    sniper_entries = np.zeros(n, dtype=bool)
    sniper_exits = np.zeros(n, dtype=bool)
    vzo_entries = np.zeros(n, dtype=bool)
    vzo_exits = np.zeros(n, dtype=bool)

    if use_sniper:
        sniper = SniperProX.run(
            close, high, low, volume,
            length=sniper_length,
            ma_type=sniper_ma_type,
            overbought_oversold=sniper_ob_os,
        )
        sniper_entries = ~np.isnan(np.asarray(sniper.major_buy, dtype=np.float64))
        sniper_exits = ~np.isnan(np.asarray(sniper.major_sell, dtype=np.float64))

    if use_vzo:
        vzo = VZOProX.run(
            close, volume,
            vzo_length=vzo_length,
            ma_type=vzo_ma_type,
            minor_buy_val=vzo_minor_buy,
            minor_sell_val=vzo_minor_sell,
        )
        vzo_entries = ~np.isnan(np.asarray(vzo.major_buy, dtype=np.float64))
        vzo_exits = ~np.isnan(np.asarray(vzo.major_sell, dtype=np.float64))

    if combine_mode == "and":
        if use_sniper and use_vzo:
            entries = sniper_entries & vzo_entries
            exits = sniper_exits | vzo_exits
        elif use_sniper:
            entries = sniper_entries
            exits = sniper_exits
        else:
            entries = vzo_entries
            exits = vzo_exits
    else:  # "or"
        entries = sniper_entries | vzo_entries
        exits = sniper_exits | vzo_exits

    if isinstance(close, pd.Series):
        entries = pd.Series(entries, index=close.index, name="entries")
        exits = pd.Series(exits, index=close.index, name="exits")

    return entries, exits
