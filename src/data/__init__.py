"""UpTrade data pipeline package."""
try:
    from src.data.polygon_client import PolygonClient, POLYGON_TIMEFRAME_MAP, CRYPTO_SYMBOL_MAP
except ImportError:
    PolygonClient = None  # type: ignore[assignment,misc]
    POLYGON_TIMEFRAME_MAP = {}  # type: ignore[assignment]
    CRYPTO_SYMBOL_MAP = {}  # type: ignore[assignment]

from src.data.db import get_engine, get_connection, reset_engine, check_health
from src.data.tsdb import (
    write_ohlcv,
    read_ohlcv,
    get_latest_timestamp,
    get_ohlcv_stats,
    write_signals,
    read_signals,
)

__all__ = [
    "PolygonClient",
    "POLYGON_TIMEFRAME_MAP",
    "CRYPTO_SYMBOL_MAP",
    "get_engine",
    "get_connection",
    "reset_engine",
    "check_health",
    "write_ohlcv",
    "read_ohlcv",
    "get_latest_timestamp",
    "get_ohlcv_stats",
    "write_signals",
    "read_signals",
]
