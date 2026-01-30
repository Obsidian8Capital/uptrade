"""Dominant Cycle Analysis — Heatmap, composite waveform, and statistics.

Streamlit page that visualizes dominant cycles detected across multiple
timeframes, reconstructs composite waveforms, and provides cycle statistics.

Schema reference (dominant_cycles table):
    time, symbol, timeframe, method, period, power, composite
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from src.data.db import get_connection

# Graceful import for charts module (created by PRP-012, may not exist yet)
try:
    from src.dashboard.components.charts import create_candlestick_chart
except ImportError:
    create_candlestick_chart = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERIOD_BINS: list[int] = [5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597]

DEFAULT_TIMEFRAMES: list[str] = ["5m", "1h", "4h", "1d"]

SYMBOLS: list[str] = ["X:BTCUSD", "X:ETHUSD", "X:SOLUSD"]

TIME_RANGE_MAP: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_TF_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def build_heatmap_matrix(
    cycle_data: pd.DataFrame,
    timeframes: list[str] | None = None,
) -> pd.DataFrame:
    """Build period x timeframe heatmap matrix from cycle data.

    Periods are binned to the nearest Fibonacci-like value in ``PERIOD_BINS``.
    Each cell holds the mean power for that (period_bin, timeframe) pair.

    Args:
        cycle_data: DataFrame with at least ``period``, ``timeframe``, and
            ``power`` columns.
        timeframes: Ordered list of timeframe strings for columns.  Defaults
            to ``DEFAULT_TIMEFRAMES``.

    Returns:
        DataFrame indexed by period_bin with timeframe columns.
    """
    if timeframes is None:
        timeframes = DEFAULT_TIMEFRAMES

    if cycle_data.empty:
        return pd.DataFrame(0.0, index=PERIOD_BINS, columns=timeframes)

    df = cycle_data.copy()
    df["period_bin"] = df["period"].apply(
        lambda p: min(PERIOD_BINS, key=lambda b: abs(b - p))
    )

    agg = df.groupby(["period_bin", "timeframe"])["power"].mean().reset_index()
    matrix = agg.pivot(index="period_bin", columns="timeframe", values="power")
    matrix = matrix.reindex(columns=timeframes)
    matrix = matrix.reindex(index=sorted(matrix.index))
    matrix = matrix.fillna(0.0)
    return matrix


def find_dominant_cycles(matrix: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Find the dominant cycle (maximum power) per timeframe.

    Args:
        matrix: Heatmap matrix from :func:`build_heatmap_matrix`.

    Returns:
        Mapping of ``timeframe -> {"period": int, "power": float}``.
    """
    result: dict[str, dict[str, Any]] = {}
    for tf in matrix.columns:
        col = matrix[tf]
        if col.max() > 0:
            dominant_period = col.idxmax()
            result[tf] = {"period": int(dominant_period), "power": float(col.max())}
    return result


def generate_composite_waveform(
    dominant_cycles: list[dict[str, Any]],
    n_bars: int = 500,
) -> np.ndarray:
    """Reconstruct composite waveform from dominant cycles as a sine sum.

    Each cycle contributes ``power * sin(2 * pi * t / period)`` to the
    composite signal.

    Args:
        dominant_cycles: List of dicts with ``period`` and ``power`` keys.
        n_bars: Number of bars (sample points) to generate.

    Returns:
        1-D numpy array of length *n_bars*.
    """
    t = np.arange(n_bars, dtype=np.float64)
    composite = np.zeros(n_bars, dtype=np.float64)
    for cycle in dominant_cycles:
        amplitude = float(cycle.get("power", 1.0))
        period = float(cycle.get("period", 20))
        if period > 0:
            composite += amplitude * np.sin(2 * np.pi * t / period)
    return composite


def period_to_calendar(period_bars: float, timeframe: str) -> str:
    """Convert a bar count to an approximate human-readable calendar duration.

    Args:
        period_bars: Number of bars representing one full cycle period.
        timeframe: Timeframe string (e.g. ``"5m"``, ``"1h"``).

    Returns:
        Formatted string such as ``"4.2h"`` or ``"2.1d"``.
    """
    minutes = period_bars * _TF_MINUTES.get(timeframe, 60)
    if minutes < 60:
        return f"{minutes:.0f}m"
    if minutes < 1440:
        return f"{minutes / 60:.1f}h"
    if minutes < 43200:
        return f"{minutes / 1440:.1f}d"
    if minutes < 525600:
        return f"{minutes / 43200:.1f}mo"
    return f"{minutes / 525600:.1f}y"


def compute_convergence_score(dominant: dict[str, dict[str, Any]]) -> float:
    """Compute a 0-1 convergence score across timeframes.

    A score of 1.0 means all timeframes share the same dominant period.
    The score decreases as dominant periods diverge.

    Args:
        dominant: Output of :func:`find_dominant_cycles`.

    Returns:
        Float in [0, 1].
    """
    if len(dominant) < 2:
        return 0.0
    periods = [v["period"] for v in dominant.values()]
    mean_period = float(np.mean(periods))
    if mean_period == 0:
        return 0.0
    std_period = float(np.std(periods))
    cv = std_period / mean_period  # coefficient of variation
    return max(0.0, 1.0 - cv)


def composite_direction(waveform: np.ndarray) -> str:
    """Determine the current direction of the composite waveform.

    Compares the last two values to decide rising/falling/flat.

    Args:
        waveform: 1-D array from :func:`generate_composite_waveform`.

    Returns:
        One of ``"Rising"``, ``"Falling"``, or ``"Flat"``.
    """
    if len(waveform) < 2:
        return "Flat"
    diff = waveform[-1] - waveform[-2]
    if diff > 1e-9:
        return "Rising"
    if diff < -1e-9:
        return "Falling"
    return "Flat"


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------


@st.cache_data(ttl=300, show_spinner="Loading cycle data...")
def load_cycle_data(
    symbol: str,
    method: str,
    since: datetime,
) -> pd.DataFrame:
    """Query dominant_cycles table for the given filters.

    Args:
        symbol: Trading pair symbol.
        method: Detection method (``"goertzel"`` or ``"hurst"``).
        since: Earliest timestamp to include.

    Returns:
        DataFrame with columns matching the dominant_cycles schema.
    """
    query = text(
        """
        SELECT time, symbol, timeframe, method, period, power, composite
        FROM dominant_cycles
        WHERE symbol = :symbol
          AND method = :method
          AND time >= :since
        ORDER BY time DESC
        """
    )
    try:
        with get_connection() as conn:
            df = pd.read_sql(query, conn, params={"symbol": symbol, "method": method, "since": since})
        return df
    except Exception as exc:
        st.warning(f"Could not load cycle data: {exc}")
        return pd.DataFrame(columns=["time", "symbol", "timeframe", "method", "period", "power", "composite"])


@st.cache_data(ttl=300, show_spinner="Loading OHLCV data...")
def load_ohlcv(symbol: str, timeframe: str, n_candles: int) -> pd.DataFrame:
    """Fetch recent OHLCV bars from the database.

    Args:
        symbol: Trading pair symbol.
        timeframe: Candle timeframe (e.g. ``"1h"``).
        n_candles: Maximum number of candles to return.

    Returns:
        DataFrame with OHLCV columns.
    """
    query = text(
        """
        SELECT time, open, high, low, close, volume
        FROM ohlcv
        WHERE symbol = :symbol AND timeframe = :timeframe
        ORDER BY time DESC
        LIMIT :limit
        """
    )
    try:
        with get_connection() as conn:
            df = pd.read_sql(query, conn, params={"symbol": symbol, "timeframe": timeframe, "limit": n_candles})
        if not df.empty:
            df = df.sort_values("time").reset_index(drop=True)
        return df
    except Exception as exc:
        st.warning(f"Could not load OHLCV data: {exc}")
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])


# ---------------------------------------------------------------------------
# Chart Builders
# ---------------------------------------------------------------------------


def create_heatmap_figure(
    matrix: pd.DataFrame,
    dominant: dict[str, dict[str, Any]],
) -> go.Figure:
    """Build a Plotly heatmap figure with dominant-cycle annotations.

    Args:
        matrix: Heatmap matrix (period_bin x timeframe).
        dominant: Dominant cycles per timeframe.

    Returns:
        Plotly Figure.
    """
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=matrix.columns.tolist(),
            y=matrix.index.tolist(),
            colorscale="Inferno",
            colorbar=dict(title="Power"),
            hovertemplate="Period: %{y}<br>Timeframe: %{x}<br>Power: %{z:.4f}<extra></extra>",
        )
    )

    # Annotate dominant cycle per timeframe
    for tf, info in dominant.items():
        if tf in matrix.columns:
            fig.add_annotation(
                x=tf,
                y=info["period"],
                text=f"{info['period']}",
                showarrow=True,
                arrowhead=2,
                arrowcolor="cyan",
                font=dict(color="cyan", size=12, family="monospace"),
                bgcolor="rgba(0,0,0,0.6)",
            )

    fig.update_layout(
        title="Cycle Power Heatmap (Period x Timeframe)",
        xaxis_title="Timeframe",
        yaxis_title="Period (bars)",
        yaxis=dict(type="log"),
        height=500,
        template="plotly_dark",
    )
    return fig


def create_composite_overlay_figure(
    ohlcv: pd.DataFrame,
    waveform: np.ndarray,
) -> go.Figure:
    """Build a candlestick chart with composite waveform overlay.

    Args:
        ohlcv: OHLCV DataFrame (must contain time, open, high, low, close).
        waveform: Composite waveform array (same length as ohlcv or trimmed).

    Returns:
        Plotly Figure with dual y-axes.
    """
    n = min(len(ohlcv), len(waveform))
    ohlcv_trimmed = ohlcv.iloc[:n]
    waveform_trimmed = waveform[:n]

    fig = go.Figure()

    # Candlestick on primary y-axis
    fig.add_trace(
        go.Candlestick(
            x=ohlcv_trimmed["time"],
            open=ohlcv_trimmed["open"],
            high=ohlcv_trimmed["high"],
            low=ohlcv_trimmed["low"],
            close=ohlcv_trimmed["close"],
            name="Price",
            yaxis="y",
        )
    )

    # Composite waveform on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=ohlcv_trimmed["time"],
            y=waveform_trimmed,
            mode="lines",
            name="Composite Waveform",
            line=dict(color="cyan", width=2),
            yaxis="y2",
        )
    )

    fig.update_layout(
        title="Price with Composite Cycle Waveform",
        xaxis_title="Time",
        yaxis=dict(title="Price", side="left"),
        yaxis2=dict(title="Composite", side="right", overlaying="y"),
        height=550,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Streamlit Page
# ---------------------------------------------------------------------------

def main() -> None:
    """Render the Dominant Cycle Analysis page."""

    st.title("Dominant Cycle Analysis")

    # --- Section A: Controls ---------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        symbol = st.selectbox("Symbol", SYMBOLS, index=0)
    with col2:
        method = st.selectbox("Method", ["goertzel", "hurst"], index=0)
    with col3:
        time_range = st.selectbox("Time Range", list(TIME_RANGE_MAP.keys()), index=1)
    with col4:
        n_candles = st.slider("Candles", 100, 1000, 500)

    since = datetime.now(tz=timezone.utc) - TIME_RANGE_MAP[time_range]

    # Load data
    cycle_data = load_cycle_data(symbol, method, since)

    if cycle_data.empty:
        st.info("No cycle data found for the selected filters. Run cycle detection first.")
        st.stop()

    # Determine available timeframes from data, preserving default order
    available_tfs = [tf for tf in DEFAULT_TIMEFRAMES if tf in cycle_data["timeframe"].unique()]
    if not available_tfs:
        available_tfs = sorted(cycle_data["timeframe"].unique().tolist())

    # --- Section B: Cycle Heatmap -----------------------------------------------
    st.header("Cycle Heatmap")

    matrix = build_heatmap_matrix(cycle_data, timeframes=available_tfs)
    dominant = find_dominant_cycles(matrix)

    heatmap_fig = create_heatmap_figure(matrix, dominant)
    st.plotly_chart(heatmap_fig, use_container_width=True)

    # Summary table
    if dominant:
        summary_rows = []
        for tf, info in dominant.items():
            summary_rows.append(
                {
                    "Timeframe": tf,
                    "Dominant Period (bars)": info["period"],
                    "Calendar Duration": period_to_calendar(info["period"], tf),
                    "Power": f"{info['power']:.4f}",
                }
            )
        st.subheader("Dominant Cycles Summary")
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # --- Section C: Composite Waveform on Price ---------------------------------
    st.header("Composite Waveform on Price")

    # Use the first available timeframe for OHLCV overlay
    overlay_tf = st.selectbox("Overlay Timeframe", available_tfs, index=0, key="overlay_tf")

    ohlcv = load_ohlcv(symbol, overlay_tf, n_candles)

    # Collect dominant cycles as list for waveform generation
    cycle_list = [{"period": v["period"], "power": v["power"]} for v in dominant.values()]
    waveform = generate_composite_waveform(cycle_list, n_bars=n_candles)

    if not ohlcv.empty:
        overlay_fig = create_composite_overlay_figure(ohlcv, waveform)
        st.plotly_chart(overlay_fig, use_container_width=True)
    else:
        st.info("No OHLCV data available for the selected timeframe.")
        # Still show waveform standalone
        standalone_fig = go.Figure()
        standalone_fig.add_trace(
            go.Scatter(
                y=waveform,
                mode="lines",
                name="Composite Waveform",
                line=dict(color="cyan", width=2),
            )
        )
        standalone_fig.update_layout(
            title="Composite Waveform (standalone)",
            yaxis_title="Amplitude",
            xaxis_title="Bar",
            height=400,
            template="plotly_dark",
        )
        st.plotly_chart(standalone_fig, use_container_width=True)

    # --- Section D: Statistics --------------------------------------------------
    st.header("Cycle Statistics")

    stat_cols = st.columns(4)

    all_periods = [v["period"] for v in dominant.values()] if dominant else []

    with stat_cols[0]:
        if all_periods:
            shortest = min(all_periods)
            tf_for_shortest = [tf for tf, v in dominant.items() if v["period"] == shortest][0]
            st.metric(
                "Shortest Active Cycle",
                f"{shortest} bars",
                delta=period_to_calendar(shortest, tf_for_shortest),
            )
        else:
            st.metric("Shortest Active Cycle", "N/A")

    with stat_cols[1]:
        if all_periods:
            longest = max(all_periods)
            tf_for_longest = [tf for tf, v in dominant.items() if v["period"] == longest][0]
            st.metric(
                "Longest Active Cycle",
                f"{longest} bars",
                delta=period_to_calendar(longest, tf_for_longest),
            )
        else:
            st.metric("Longest Active Cycle", "N/A")

    with stat_cols[2]:
        score = compute_convergence_score(dominant)
        st.metric("Convergence Score", f"{score:.2f}", delta="aligned" if score > 0.7 else "divergent")

    with stat_cols[3]:
        direction = composite_direction(waveform)
        delta_color = "normal" if direction == "Rising" else ("inverse" if direction == "Falling" else "off")
        st.metric("Composite Direction", direction, delta=direction, delta_color=delta_color)


# Entry point for Streamlit multi-page apps
main()
