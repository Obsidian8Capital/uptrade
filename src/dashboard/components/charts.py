"""Reusable Plotly chart components for UpTrade dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _resolve_col(df: pd.DataFrame, *candidates: str) -> pd.Series:
    """Return the first matching column from *candidates*, or an empty Series."""
    for name in candidates:
        if name in df.columns:
            return df[name]
    return pd.Series(dtype=float)


def _resolve_time(df: pd.DataFrame) -> pd.Series | pd.Index:
    """Return the time axis — either a 'time' column or the DataFrame index."""
    if "time" in df.columns:
        return df["time"]
    return df.index


# ---------------------------------------------------------------------------
# Candlestick
# ---------------------------------------------------------------------------

def create_candlestick_chart(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Create an OHLCV candlestick chart with a volume sub-plot.

    Accepts both lowercase (``open``) and VBT-style capitalised (``Open``)
    column names.  The time axis is taken from a ``time`` column when present,
    otherwise from the DataFrame index.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
    )

    time_col = _resolve_time(df)
    open_col = _resolve_col(df, "open", "Open")
    high_col = _resolve_col(df, "high", "High")
    low_col = _resolve_col(df, "low", "Low")
    close_col = _resolve_col(df, "close", "Close")
    vol_col = _resolve_col(df, "volume", "Volume")

    fig.add_trace(
        go.Candlestick(
            x=time_col,
            open=open_col,
            high=high_col,
            low=low_col,
            close=close_col,
            name="OHLCV",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1,
        col=1,
    )

    if len(vol_col) > 0:
        colors = [
            "#26a69a" if c >= o else "#ef5350"
            for c, o in zip(close_col, open_col)
        ]
        fig.add_trace(
            go.Bar(
                x=time_col,
                y=vol_col,
                name="Volume",
                marker_color=colors,
                opacity=0.5,
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=600,
    )
    return fig


# ---------------------------------------------------------------------------
# Signal markers
# ---------------------------------------------------------------------------

def add_signal_markers(fig: go.Figure, signals_df: pd.DataFrame) -> go.Figure:
    """Overlay buy / sell triangle markers on a candlestick figure.

    Expects ``signals_df`` to contain at least ``signal`` (1 = buy, -1 = sell)
    and a ``time`` column (or DatetimeIndex).  Optional ``price``, ``low``,
    ``high`` columns are used for the y-position; if absent the markers are
    placed at *y = 0*.
    """
    time_col = _resolve_time(signals_df)

    buys = signals_df[signals_df["signal"] == 1]
    sells = signals_df[signals_df["signal"] == -1]

    if len(buys) > 0:
        buy_time = time_col[buys.index] if isinstance(time_col, pd.Series) else buys.index
        buy_y = _resolve_col(buys, "price", "low")
        fig.add_trace(
            go.Scatter(
                x=buy_time,
                y=buy_y if len(buy_y) > 0 else None,
                mode="markers",
                name="Buy Signal",
                marker=dict(symbol="triangle-up", size=12, color="#00e676"),
            ),
            row=1,
            col=1,
        )

    if len(sells) > 0:
        sell_time = time_col[sells.index] if isinstance(time_col, pd.Series) else sells.index
        sell_y = _resolve_col(sells, "price", "high")
        fig.add_trace(
            go.Scatter(
                x=sell_time,
                y=sell_y if len(sell_y) > 0 else None,
                mode="markers",
                name="Sell Signal",
                marker=dict(symbol="triangle-down", size=12, color="#ff1744"),
            ),
            row=1,
            col=1,
        )

    return fig


# ---------------------------------------------------------------------------
# Indicator overlay
# ---------------------------------------------------------------------------

def add_indicator_overlay(
    fig: go.Figure,
    df: pd.DataFrame,
    name: str,
    color: str = "blue",
) -> go.Figure:
    """Add an indicator line on a secondary y-axis."""
    time_col = _resolve_time(df)
    value_col = _resolve_col(df, "value", "Value")

    fig.add_trace(
        go.Scatter(
            x=time_col,
            y=value_col,
            name=name,
            line=dict(color=color, width=1.5),
            yaxis="y3",
        )
    )
    fig.update_layout(
        yaxis3=dict(overlaying="y", side="right", showgrid=False),
    )
    return fig


# ---------------------------------------------------------------------------
# P&L chart
# ---------------------------------------------------------------------------

def create_pnl_chart(df: pd.DataFrame) -> go.Figure:
    """Create a cumulative P&L area chart.

    Expects ``df`` to have ``time`` and ``pnl`` columns (or a DatetimeIndex).
    """
    time_col = _resolve_time(df)
    pnl_col = _resolve_col(df, "pnl", "PnL", "Pnl")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=time_col,
            y=pnl_col,
            fill="tozeroy",
            name="P&L",
            line=dict(color="#26a69a"),
            fillcolor="rgba(38,166,154,0.3)",
        )
    )
    fig.update_layout(
        title="Cumulative P&L",
        template="plotly_dark",
        height=400,
    )
    return fig
