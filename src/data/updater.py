"""Scheduled data update service for continuous Polygon.io polling."""
import asyncio
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config.bot_config import load_all_configs
from src.data.polygon_client import PolygonClient, CRYPTO_SYMBOL_MAP
from src.data.tsdb import write_ohlcv, get_latest_timestamp
from src.logging_config import get_logger

logger = get_logger("data_updater")

# Default poll intervals: 80% of timeframe duration in seconds
DEFAULT_POLL_INTERVALS = {
    "1m": 48,
    "5m": 240,
    "15m": 720,
    "30m": 1440,
    "1h": 2880,
    "4h": 11520,
    "1d": 69120,
    "1w": 483840,
}


class DataUpdaterService:
    """Continuously polls Polygon.io for new candles and writes to TimescaleDB."""

    def __init__(
        self,
        symbols: Optional[list[str]] = None,
        timeframes: Optional[list[str]] = None,
        settings=None,
        poll_intervals: Optional[dict[str, float]] = None,
        health_file: str = "/tmp/updater_health",
    ):
        """Initialize the data updater service.

        Args:
            symbols: List of Polygon symbols (e.g., ["X:BTCUSD"]).
            timeframes: List of timeframes (e.g., ["1m", "1h"]).
            settings: Optional Settings instance.
            poll_intervals: Custom poll interval overrides per timeframe.
            health_file: Path to write heartbeat timestamps.
        """
        self.symbols = symbols or ["X:BTCUSD"]
        self.timeframes = timeframes or ["1m"]
        self.client = PolygonClient(settings=settings)
        self._poll_intervals = poll_intervals or {}
        self._health_file = health_file
        self._running = False

    def get_poll_interval(self, timeframe: str) -> float:
        """Get polling interval in seconds for a timeframe.

        Uses custom override if set, otherwise defaults to 80% of timeframe duration.
        """
        if timeframe in self._poll_intervals:
            return self._poll_intervals[timeframe]
        return DEFAULT_POLL_INTERVALS.get(timeframe, 60.0)

    def startup_backfill(self) -> None:
        """Run incremental update for all symbol/timeframe pairs on startup."""
        logger.info(
            "Starting backfill for %d symbols x %d timeframes",
            len(self.symbols), len(self.timeframes),
        )
        total_rows = 0
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                try:
                    df = self.client.incremental_update(
                        symbol, timeframe,
                        read_fn=get_latest_timestamp,
                        write_fn=write_ohlcv,
                    )
                    rows = len(df) if df is not None else 0
                    total_rows += rows
                    if rows > 0:
                        logger.info("Backfill: %s %s — %d rows", symbol, timeframe, rows)
                except Exception as e:
                    logger.error("Backfill failed for %s %s: %s", symbol, timeframe, e)
        logger.info("Startup backfill complete: %d total rows", total_rows)

    def _update_once(self, symbol: str, timeframe: str) -> None:
        """Single poll cycle for one symbol/timeframe."""
        try:
            df = self.client.incremental_update(
                symbol, timeframe,
                read_fn=get_latest_timestamp,
                write_fn=write_ohlcv,
            )
            rows = len(df) if df is not None else 0
            if rows > 0:
                logger.info("Update: %s %s — %d new rows", symbol, timeframe, rows)

            # Write heartbeat
            Path(self._health_file).write_text(
                datetime.now(timezone.utc).isoformat()
            )
        except Exception as e:
            logger.error("Poll failed for %s %s: %s", symbol, timeframe, e)

    async def _poll_loop(self, symbol: str, timeframe: str) -> None:
        """Async polling loop for one symbol/timeframe pair."""
        interval = self.get_poll_interval(timeframe)
        logger.info("Poll loop started: %s %s (interval=%.0fs)", symbol, timeframe, interval)

        while self._running:
            try:
                await asyncio.to_thread(self._update_once, symbol, timeframe)
            except Exception as e:
                logger.error("Poll loop error for %s %s: %s", symbol, timeframe, e)
                await asyncio.sleep(30)
                continue
            await asyncio.sleep(interval)

    async def run(self) -> None:
        """Start the data updater service."""
        self._running = True

        # Register signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.stop)

        pairs = [(s, tf) for s in self.symbols for tf in self.timeframes]
        logger.info("DataUpdater starting with %d symbol/timeframe pairs", len(pairs))

        # Startup backfill
        await asyncio.to_thread(self.startup_backfill)

        # Create concurrent poll tasks
        tasks = [
            asyncio.create_task(self._poll_loop(symbol, timeframe))
            for symbol, timeframe in pairs
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

        logger.info("DataUpdater shut down gracefully")

    def stop(self) -> None:
        """Request graceful shutdown."""
        logger.info("Stop requested")
        self._running = False

    @classmethod
    def from_bot_configs(
        cls,
        config_dir: str = "src/config/examples/",
        settings=None,
    ) -> "DataUpdaterService":
        """Create updater from bot deployment configs.

        Extracts unique symbols and timeframes from all YAML bot configs.
        """
        configs = load_all_configs(config_dir)
        symbols = set()
        timeframes = set()

        for config in configs:
            # Use symbol_override from data config, or map pair to Polygon format
            if config.data.symbol_override:
                symbols.add(config.data.symbol_override)
            else:
                pair = config.market.pair
                polygon_sym = CRYPTO_SYMBOL_MAP.get(pair, f"X:{pair.replace('-', '')}")
                symbols.add(polygon_sym)

            timeframes.add(config.market.timeframe.value)

        logger.info(
            "from_bot_configs: %d configs → %d symbols, %d timeframes",
            len(configs), len(symbols), len(timeframes),
        )
        return cls(
            symbols=sorted(symbols),
            timeframes=sorted(timeframes),
            settings=settings,
        )
