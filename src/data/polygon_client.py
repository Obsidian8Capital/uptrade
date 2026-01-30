"""Polygon.io data ingestion client wrapping VectorBT Pro's PolygonData."""
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import pandas as pd
import vectorbtpro as vbt

from src.config.settings import Settings
from src.logging_config import get_logger

logger = get_logger("polygon_client")

# Map our timeframe strings to VBT PolygonData format
POLYGON_TIMEFRAME_MAP = {
    "1m": "1 minute",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "30m": "30 minutes",
    "1h": "1 hour",
    "4h": "4 hours",
    "1d": "1 day",
    "1w": "1 week",
}

# Map common pair names to Polygon crypto symbol format
CRYPTO_SYMBOL_MAP = {
    "BTCUSD": "X:BTCUSD",
    "ETHUSD": "X:ETHUSD",
    "SOLUSD": "X:SOLUSD",
    "BTCUSDT": "X:BTCUSD",
    "ETHUSDC": "X:ETHUSD",
    "SOLUSDT": "X:SOLUSD",
    "BTC-USDT": "X:BTCUSD",
    "ETH-USDC": "X:ETHUSD",
    "SOL-USDT": "X:SOLUSD",
    "BTC-USD": "X:BTCUSD",
    "ETH-USD": "X:ETHUSD",
    "SOL-USD": "X:SOLUSD",
}


def create_polygon_client(settings: Optional[Settings] = None) -> "PolygonClient":
    """Factory function to create a PolygonClient."""
    return PolygonClient(settings=settings)


class PolygonClient:
    """Polygon.io data ingestion client using VBT Pro's PolygonData."""

    def __init__(self, settings: Optional[Settings] = None, request_delay: float = 0.5):
        """Initialize the Polygon client.

        Args:
            settings: Application settings. If None, loads defaults.
            request_delay: Seconds to wait between API calls (rate limiting).
        """
        self.settings = settings or Settings()
        self.request_delay = request_delay

        # Configure VBT with Polygon API key
        if self.settings.polygon_api_key:
            vbt.PolygonData.set_custom_settings(
                client_config=dict(api_key=self.settings.polygon_api_key)
            )
            logger.info("Polygon API key configured")
        else:
            logger.warning("No Polygon API key set — data pulls will fail")

    def _resolve_symbol(self, symbol: str) -> str:
        """Resolve a symbol to Polygon format if mapped."""
        return CRYPTO_SYMBOL_MAP.get(symbol, symbol)

    def _resolve_timeframe(self, timeframe: str) -> str:
        """Resolve a timeframe to VBT PolygonData format."""
        vbt_tf = POLYGON_TIMEFRAME_MAP.get(timeframe)
        if vbt_tf is None:
            raise ValueError(
                f"Unknown timeframe '{timeframe}'. Valid: {list(POLYGON_TIMEFRAME_MAP.keys())}"
            )
        return vbt_tf

    def pull_ohlcv(
        self, symbol: str, timeframe: str, start: str, end: str
    ) -> pd.DataFrame:
        """Pull OHLCV data from Polygon.io via VBT.

        Args:
            symbol: Ticker symbol (e.g., "X:BTCUSD" or "BTC-USDT").
            timeframe: Candle timeframe (e.g., "1m", "1h", "1d").
            start: Start date string (e.g., "2024-01-01").
            end: End date string (e.g., "2024-12-31").

        Returns:
            DataFrame with columns: open, high, low, close, volume, vwap, trade_count,
            symbol, timeframe. DatetimeIndex named 'time'.
        """
        polygon_symbol = self._resolve_symbol(symbol)
        vbt_timeframe = self._resolve_timeframe(timeframe)

        logger.info(
            "Pulling OHLCV: symbol=%s timeframe=%s start=%s end=%s",
            polygon_symbol, timeframe, start, end,
        )

        try:
            data = vbt.PolygonData.pull(
                polygon_symbol,
                timeframe=vbt_timeframe,
                start=start,
                end=end,
            )
            df = data.get()

            if df is None or df.empty:
                logger.warning("No data returned for %s %s", polygon_symbol, timeframe)
                return pd.DataFrame()

            # Rename columns to lowercase matching TimescaleDB schema
            rename_map = {
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
            df = df.rename(columns=rename_map)

            # Add VWAP if available
            try:
                vwap_data = data.get("VWAP")
                if vwap_data is not None and not vwap_data.empty:
                    df["vwap"] = vwap_data.values if hasattr(vwap_data, 'values') else vwap_data
                else:
                    df["vwap"] = None
            except Exception:
                df["vwap"] = None

            # Add trade count if available
            try:
                tx_data = data.get("Transactions")
                if tx_data is not None and not tx_data.empty:
                    df["trade_count"] = tx_data.values if hasattr(tx_data, 'values') else tx_data
                else:
                    df["trade_count"] = None
            except Exception:
                df["trade_count"] = None

            # Add metadata columns
            df["symbol"] = polygon_symbol
            df["timeframe"] = timeframe

            # Set index name
            df.index.name = "time"

            # Keep only expected columns
            expected_cols = [
                "open", "high", "low", "close", "volume",
                "vwap", "trade_count", "symbol", "timeframe",
            ]
            df = df[[c for c in expected_cols if c in df.columns]]

            logger.info(
                "Pulled %d rows for %s %s (%s to %s)",
                len(df), polygon_symbol, timeframe,
                df.index.min() if len(df) > 0 else "N/A",
                df.index.max() if len(df) > 0 else "N/A",
            )
            return df

        except Exception as e:
            logger.error("Failed to pull data for %s %s: %s", polygon_symbol, timeframe, e)
            return pd.DataFrame()

    def backfill(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        write_fn: Optional[Callable] = None,
    ) -> pd.DataFrame:
        """Pull historical data and optionally write to DB.

        Args:
            symbol: Ticker symbol.
            timeframe: Candle timeframe.
            start: Start date.
            end: End date.
            write_fn: Optional callback to write data (e.g., tsdb.write_ohlcv).
        """
        df = self.pull_ohlcv(symbol, timeframe, start, end)

        if not df.empty and write_fn is not None:
            write_fn(df, symbol=self._resolve_symbol(symbol), timeframe=timeframe)
            logger.info("Backfill written: %s %s, %d rows", symbol, timeframe, len(df))

        return df

    def backfill_batch(
        self,
        symbols: list[str],
        timeframes: list[str],
        start: str,
        end: str,
        write_fn: Optional[Callable] = None,
    ) -> dict[tuple[str, str], int]:
        """Batch backfill multiple symbol/timeframe combinations.

        Args:
            symbols: List of ticker symbols.
            timeframes: List of timeframes.
            start: Start date.
            end: End date.
            write_fn: Optional DB write callback.

        Returns:
            Dict mapping (symbol, timeframe) to row count.
        """
        results = {}
        total_rows = 0

        for symbol in symbols:
            for timeframe in timeframes:
                df = self.backfill(symbol, timeframe, start, end, write_fn)
                row_count = len(df)
                results[(symbol, timeframe)] = row_count
                total_rows += row_count

                # Rate limiting
                time.sleep(self.request_delay)

        logger.info(
            "Batch backfill complete: %d combinations, %d total rows",
            len(results), total_rows,
        )
        return results

    def incremental_update(
        self,
        symbol: str,
        timeframe: str,
        read_fn: Optional[Callable] = None,
        write_fn: Optional[Callable] = None,
    ) -> pd.DataFrame:
        """Pull only new data since last DB entry.

        Args:
            symbol: Ticker symbol.
            timeframe: Candle timeframe.
            read_fn: Callback to get latest timestamp (e.g., tsdb.get_latest_timestamp).
            write_fn: Callback to write data.

        Returns:
            DataFrame of new data.
        """
        polygon_symbol = self._resolve_symbol(symbol)

        # Determine start time
        latest_ts = None
        if read_fn is not None:
            latest_ts = read_fn(polygon_symbol, timeframe)

        if latest_ts is not None:
            start = (latest_ts + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
            logger.info("No existing data for %s %s, defaulting to 7 days ago", symbol, timeframe)

        end = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        df = self.pull_ohlcv(symbol, timeframe, start, end)

        if not df.empty and write_fn is not None:
            write_fn(df, symbol=polygon_symbol, timeframe=timeframe)
            logger.info("Incremental update: %s %s, %d new rows", symbol, timeframe, len(df))

        return df

    def incremental_update_batch(
        self,
        symbols: list[str],
        timeframes: list[str],
        read_fn: Optional[Callable] = None,
        write_fn: Optional[Callable] = None,
    ) -> dict[tuple[str, str], int]:
        """Batch incremental update for multiple symbol/timeframe combinations.

        Returns:
            Dict mapping (symbol, timeframe) to row count of new data.
        """
        results = {}
        total_rows = 0

        for symbol in symbols:
            for timeframe in timeframes:
                df = self.incremental_update(symbol, timeframe, read_fn, write_fn)
                row_count = len(df)
                results[(symbol, timeframe)] = row_count
                total_rows += row_count

                # Rate limiting
                time.sleep(self.request_delay)

        logger.info(
            "Batch incremental update: %d combinations, %d new rows",
            len(results), total_rows,
        )
        return results
