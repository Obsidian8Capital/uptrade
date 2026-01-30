"""TimescaleDB read/write functions for OHLCV and indicator signals."""
import json
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import sqlalchemy as sa

from src.data.db import get_engine, get_connection
from src.logging_config import get_logger

logger = get_logger("tsdb")


def write_ohlcv(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    chunk_size: int = 5000,
) -> int:
    """Write OHLCV data to TimescaleDB with upsert.

    Args:
        df: DataFrame with DatetimeIndex and columns: open, high, low, close, volume
            (and optional vwap, trade_count).
        symbol: Ticker symbol.
        timeframe: Candle timeframe.
        chunk_size: Number of rows per batch insert.

    Returns:
        Number of rows written.
    """
    if df.empty:
        return 0

    # Prepare data
    write_df = df.copy()

    # Ensure index is the time column
    if write_df.index.name == "time" or isinstance(write_df.index, pd.DatetimeIndex):
        write_df = write_df.reset_index()
        if "index" in write_df.columns:
            write_df = write_df.rename(columns={"index": "time"})

    # Ensure time column exists
    if "time" not in write_df.columns:
        raise ValueError("DataFrame must have a 'time' column or DatetimeIndex")

    # Normalize column names to lowercase
    write_df.columns = [c.lower() for c in write_df.columns]

    # Add symbol/timeframe if not present
    if "symbol" not in write_df.columns:
        write_df["symbol"] = symbol
    if "timeframe" not in write_df.columns:
        write_df["timeframe"] = timeframe

    # Ensure timestamps are UTC
    if write_df["time"].dt.tz is None:
        write_df["time"] = write_df["time"].dt.tz_localize("UTC")

    # Ensure optional columns exist
    if "vwap" not in write_df.columns:
        write_df["vwap"] = None
    if "trade_count" not in write_df.columns:
        write_df["trade_count"] = None

    # Select only expected columns
    columns = ["time", "symbol", "timeframe", "open", "high", "low", "close", "volume", "vwap", "trade_count"]
    write_df = write_df[[c for c in columns if c in write_df.columns]]

    # Upsert in chunks
    upsert_sql = sa.text("""
        INSERT INTO ohlcv (time, symbol, timeframe, open, high, low, close, volume, vwap, trade_count)
        VALUES (:time, :symbol, :timeframe, :open, :high, :low, :close, :volume, :vwap, :trade_count)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            vwap = EXCLUDED.vwap,
            trade_count = EXCLUDED.trade_count
    """)

    rows_written = 0
    with get_connection() as conn:
        for start in range(0, len(write_df), chunk_size):
            chunk = write_df.iloc[start:start + chunk_size]
            records = chunk.to_dict("records")
            conn.execute(upsert_sql, records)
            rows_written += len(records)

    logger.info("write_ohlcv: %s %s, %d rows written", symbol, timeframe, rows_written)
    return rows_written


def read_ohlcv(
    symbol: str,
    timeframe: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Read OHLCV data from TimescaleDB as VBT-compatible DataFrame.

    Args:
        symbol: Ticker symbol.
        timeframe: Candle timeframe.
        start: Start datetime string (optional).
        end: End datetime string (optional).
        limit: Max rows to return (optional).

    Returns:
        DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume
        (capitalized for VBT compatibility).
    """
    query_parts = [
        "SELECT time, open, high, low, close, volume, vwap, trade_count",
        "FROM ohlcv",
        "WHERE symbol = :symbol AND timeframe = :timeframe",
    ]
    params: dict = {"symbol": symbol, "timeframe": timeframe}

    if start is not None:
        query_parts.append("AND time >= :start")
        params["start"] = start
    if end is not None:
        query_parts.append("AND time <= :end")
        params["end"] = end

    query_parts.append("ORDER BY time")

    if limit is not None:
        query_parts.append("LIMIT :limit")
        params["limit"] = limit

    query = sa.text(" ".join(query_parts))

    engine = get_engine()
    df = pd.read_sql(query, engine, params=params)

    if df.empty:
        logger.info("read_ohlcv: No data for %s %s", symbol, timeframe)
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    # Set time as DatetimeIndex
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time")

    # Rename to VBT-compatible capitalized columns
    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    df = df.rename(columns=rename_map)

    logger.info("read_ohlcv: %s %s, %d rows returned", symbol, timeframe, len(df))
    return df


def get_latest_timestamp(
    symbol: str, timeframe: str
) -> Optional[datetime]:
    """Get the latest timestamp for a symbol/timeframe in the DB.

    Args:
        symbol: Ticker symbol.
        timeframe: Candle timeframe.

    Returns:
        Latest timestamp as datetime (UTC), or None if no data.
    """
    query = sa.text(
        "SELECT MAX(time) AS latest FROM ohlcv "
        "WHERE symbol = :symbol AND timeframe = :timeframe"
    )
    with get_connection() as conn:
        result = conn.execute(query, {"symbol": symbol, "timeframe": timeframe})
        row = result.fetchone()

    if row is None or row[0] is None:
        return None

    ts = row[0]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def get_ohlcv_stats(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> pd.DataFrame:
    """Get summary statistics for stored OHLCV data.

    Args:
        symbol: Optional filter by symbol.
        timeframe: Optional filter by timeframe.

    Returns:
        DataFrame with columns: symbol, timeframe, rows, first, last.
    """
    query_parts = [
        "SELECT symbol, timeframe, COUNT(*) AS rows,",
        "MIN(time) AS first, MAX(time) AS last",
        "FROM ohlcv",
    ]
    params: dict = {}
    conditions = []

    if symbol is not None:
        conditions.append("symbol = :symbol")
        params["symbol"] = symbol
    if timeframe is not None:
        conditions.append("timeframe = :timeframe")
        params["timeframe"] = timeframe

    if conditions:
        query_parts.append("WHERE " + " AND ".join(conditions))

    query_parts.append("GROUP BY symbol, timeframe ORDER BY symbol, timeframe")

    query = sa.text(" ".join(query_parts))
    engine = get_engine()
    return pd.read_sql(query, engine, params=params)


def write_signals(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    indicator: str,
    params: Optional[dict] = None,
    chunk_size: int = 5000,
) -> int:
    """Write indicator signals to TimescaleDB.

    Args:
        df: DataFrame with DatetimeIndex and columns: signal (int), value (float).
        symbol: Ticker symbol.
        timeframe: Candle timeframe.
        indicator: Indicator name.
        params: Indicator parameters (stored as JSONB).
        chunk_size: Batch size for inserts.

    Returns:
        Number of rows written.
    """
    if df.empty:
        return 0

    write_df = df.copy()

    # Ensure index is time column
    if isinstance(write_df.index, pd.DatetimeIndex):
        write_df = write_df.reset_index()
        if "index" in write_df.columns:
            write_df = write_df.rename(columns={"index": "time"})

    if write_df.index.name == "time":
        write_df = write_df.reset_index()

    if "time" not in write_df.columns:
        raise ValueError("DataFrame must have a 'time' column or DatetimeIndex")

    # Add metadata columns
    write_df["symbol"] = symbol
    write_df["timeframe"] = timeframe
    write_df["indicator"] = indicator
    write_df["params"] = json.dumps(params) if params else None

    # Ensure timestamps are UTC
    if write_df["time"].dt.tz is None:
        write_df["time"] = write_df["time"].dt.tz_localize("UTC")

    upsert_sql = sa.text("""
        INSERT INTO indicator_signals (time, symbol, timeframe, indicator, signal, value, params)
        VALUES (:time, :symbol, :timeframe, :indicator, :signal, :value, :params)
        ON CONFLICT (time, symbol, timeframe, indicator) DO UPDATE SET
            signal = EXCLUDED.signal,
            value = EXCLUDED.value,
            params = EXCLUDED.params
    """)

    rows_written = 0
    with get_connection() as conn:
        for start_idx in range(0, len(write_df), chunk_size):
            chunk = write_df.iloc[start_idx:start_idx + chunk_size]
            records = chunk[["time", "symbol", "timeframe", "indicator", "signal", "value", "params"]].to_dict("records")
            conn.execute(upsert_sql, records)
            rows_written += len(records)

    logger.info("write_signals: %s %s %s, %d rows written", indicator, symbol, timeframe, rows_written)
    return rows_written


def read_signals(
    symbol: str,
    timeframe: str,
    indicator: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Read indicator signals from TimescaleDB.

    Args:
        symbol: Ticker symbol.
        timeframe: Candle timeframe.
        indicator: Indicator name.
        start: Start datetime string (optional).
        end: End datetime string (optional).

    Returns:
        DataFrame with DatetimeIndex and columns: signal, value, params.
    """
    query_parts = [
        "SELECT time, signal, value, params",
        "FROM indicator_signals",
        "WHERE symbol = :symbol AND timeframe = :timeframe AND indicator = :indicator",
    ]
    params_dict: dict = {
        "symbol": symbol,
        "timeframe": timeframe,
        "indicator": indicator,
    }

    if start is not None:
        query_parts.append("AND time >= :start")
        params_dict["start"] = start
    if end is not None:
        query_parts.append("AND time <= :end")
        params_dict["end"] = end

    query_parts.append("ORDER BY time")
    query = sa.text(" ".join(query_parts))

    engine = get_engine()
    df = pd.read_sql(query, engine, params=params_dict)

    if df.empty:
        return pd.DataFrame(columns=["signal", "value", "params"])

    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time")

    logger.info("read_signals: %s %s %s, %d rows", indicator, symbol, timeframe, len(df))
    return df
