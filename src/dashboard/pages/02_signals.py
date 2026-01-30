"""Page 2 — Signals: OHLCV candlestick chart with indicator signal overlays."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.components.charts import (
    create_candlestick_chart,
    add_signal_markers,
    add_indicator_overlay,
)

# ---------------------------------------------------------------------------
# Sidebar selectors
# ---------------------------------------------------------------------------

st.header("Signal Visualization")

col_sym, col_tf, col_ind = st.columns(3)
with col_sym:
    symbol = st.text_input("Symbol", value="BTC-USDT")
with col_tf:
    timeframe = st.selectbox(
        "Timeframe",
        options=["1m", "5m", "15m", "1h", "4h", "1d"],
        index=3,
    )
with col_ind:
    indicator = st.selectbox(
        "Indicator",
        options=["SniperProX", "VZOProX", "SpectralAnalysis"],
        index=0,
    )

limit = st.slider("Candles to load", min_value=50, max_value=2000, value=500, step=50)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@st.cache_data(ttl=30, show_spinner="Loading OHLCV data...")
def _load_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Load OHLCV data from TimescaleDB (graceful fallback on error)."""
    try:
        from src.data.tsdb import read_ohlcv

        df = read_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        if df.empty:
            return pd.DataFrame()
        # Normalise columns to lowercase for chart functions
        df = df.rename(columns={c: c.lower() for c in df.columns})
        df = df.reset_index()
        if "time" not in df.columns and df.index.name == "time":
            df = df.reset_index()
        return df
    except Exception as exc:  # noqa: BLE001
        st.warning(f"OHLCV load failed: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=30, show_spinner="Loading signals...")
def _load_signals(symbol: str, timeframe: str, indicator: str) -> pd.DataFrame:
    """Load indicator signals from TimescaleDB (graceful fallback)."""
    try:
        from src.data.tsdb import read_signals

        df = read_signals(symbol=symbol, timeframe=timeframe, indicator=indicator)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        return df
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Signals load failed: {exc}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------

ohlcv_df = _load_ohlcv(symbol, timeframe, limit)

if ohlcv_df.empty:
    st.info(
        f"No OHLCV data for **{symbol}** / **{timeframe}**. "
        "Ensure the data pipeline is running."
    )
else:
    fig = create_candlestick_chart(ohlcv_df, title=f"{symbol} — {timeframe}")

    signals_df = _load_signals(symbol, timeframe, indicator)
    if not signals_df.empty:
        fig = add_signal_markers(fig, signals_df)

        # Indicator overlay (value column)
        if "value" in signals_df.columns:
            fig = add_indicator_overlay(fig, signals_df, name=indicator, color="#42a5f5")

    st.plotly_chart(fig, use_container_width=True)

    # Signal history table
    st.subheader("Signal History")
    if not signals_df.empty:
        display_df = signals_df.copy()
        display_df["signal_label"] = display_df["signal"].map(
            {1: "BUY", -1: "SELL", 0: "NEUTRAL"}
        )
        st.dataframe(
            display_df[["time", "signal_label", "value"]].tail(100),
            use_container_width=True,
        )
    else:
        st.info("No signals recorded for this indicator.")
