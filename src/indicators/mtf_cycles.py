"""Multi-Timeframe Cycle Detector using SpectralAnalysis."""
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from src.indicators.nb.spectral_nb import spectral_analysis_1d_nb
from src.logging_config import get_logger

logger = get_logger("mtf_cycles")

# Predefined cycle periods (in bars) from SpectralAnalysis
DEFAULT_PERIODS = np.array([
    4.3, 8.5, 17.0, 34.1, 68.2, 136.4, 272.8, 545.6, 1636.8, 3273.6, 6547.2
])
CYCLE_NAMES = ["5d", "10d", "20d", "40d", "80d", "20w", "40w", "18m", "54m", "9y", "18y"]

DEFAULT_TIMEFRAMES = ["5m", "1h", "4h", "1d"]
METHOD_HURST = 0
METHOD_GOERTZEL = 1


def detect_cycles(
    symbol: str,
    data: dict[str, pd.DataFrame],
    timeframes: Optional[list[str]] = None,
    method: int = METHOD_GOERTZEL,
) -> dict:
    """Quick function to detect dominant cycles across timeframes."""
    detector = MTFCycleDetector(symbol=symbol, timeframes=timeframes, method=method)
    return detector.run(data)


class MTFCycleDetector:
    """Runs SpectralAnalysis across multiple timeframes to identify dominant cycles."""

    def __init__(
        self,
        symbol: str,
        timeframes: Optional[list[str]] = None,
        method: int = METHOD_GOERTZEL,
        bandwidth: float = 0.025,
        window_size: int = 618,
        scale_factor: float = 100000.0,
    ):
        """Initialize the cycle detector.

        Args:
            symbol: Ticker symbol.
            timeframes: List of timeframes to analyze.
            method: 0=Hurst bandpass, 1=Goertzel DFT.
            bandwidth: Bandpass filter bandwidth.
            window_size: Analysis window size.
            scale_factor: Output scale factor.
        """
        self.symbol = symbol
        self.timeframes = timeframes or DEFAULT_TIMEFRAMES
        self.method = method
        self.bandwidth = bandwidth
        self.window_size = window_size
        self.scale_factor = scale_factor
        self._results: dict[str, dict] = {}

    def analyze_timeframe(self, source: np.ndarray, timeframe: str) -> dict:
        """Analyze a single timeframe for dominant cycles.

        Args:
            source: 1D price array (typically hl2 = (high + low) / 2).
            timeframe: Timeframe label.

        Returns:
            Dict with dominant cycle info.
        """
        composite_mask = np.ones(len(DEFAULT_PERIODS), dtype=np.bool_)

        cycles, composite = spectral_analysis_1d_nb(
            source,
            DEFAULT_PERIODS,
            composite_mask,
            self.bandwidth,
            self.method,
            self.window_size,
            self.scale_factor,
        )

        # Extract latest bar values
        latest_cycles = cycles[-1, :]
        dominant_idx = int(np.argmax(np.abs(latest_cycles)))

        result = {
            "timeframe": timeframe,
            "dominant_period": float(DEFAULT_PERIODS[dominant_idx]),
            "dominant_cycle_name": CYCLE_NAMES[dominant_idx],
            "dominant_power": float(latest_cycles[dominant_idx]),
            "all_powers": {
                CYCLE_NAMES[i]: float(latest_cycles[i])
                for i in range(len(CYCLE_NAMES))
            },
            "composite": float(composite[-1]),
            "method": "hurst" if self.method == 0 else "goertzel",
        }

        logger.info(
            "Cycle analysis %s %s: dominant=%s (period=%.1f, power=%.4f)",
            self.symbol, timeframe,
            result["dominant_cycle_name"],
            result["dominant_period"],
            result["dominant_power"],
        )
        return result

    def run(self, data: dict[str, pd.DataFrame]) -> dict:
        """Run cycle detection across all timeframes.

        Args:
            data: Dict of {timeframe: DataFrame} where each DataFrame has
                  High and Low columns (VBT format from read_ohlcv).

        Returns:
            Dict with per-timeframe results, composite score, and suggested length.
        """
        self._results = {}

        for tf in self.timeframes:
            if tf not in data:
                logger.warning("No data for timeframe %s, skipping", tf)
                continue

            df = data[tf]
            if df.empty or len(df) < 50:
                logger.warning("Insufficient data for %s (%d rows), skipping", tf, len(df))
                continue

            # Compute hl2
            high = df["High"].values if "High" in df.columns else df["high"].values
            low = df["Low"].values if "Low" in df.columns else df["low"].values
            hl2 = (high + low) / 2.0

            result = self.analyze_timeframe(hl2, tf)
            self._results[tf] = result

        composite_score, suggested_length = self.compute_composite_score()

        return {
            "symbol": self.symbol,
            "timeframes": dict(self._results),
            "composite_score": composite_score,
            "suggested_length": suggested_length,
        }

    def compute_composite_score(self) -> tuple[float, int]:
        """Compute power-weighted average of dominant periods across timeframes.

        Returns:
            Tuple of (composite_score, suggested_length).
        """
        if not self._results:
            return 0.0, 28

        periods = [r["dominant_period"] for r in self._results.values()]
        powers = [abs(r["dominant_power"]) for r in self._results.values()]
        total_power = sum(powers)

        if total_power == 0:
            return 0.0, 28

        composite_score = sum(p * w for p, w in zip(periods, powers)) / total_power
        suggested_length = max(7, min(200, round(composite_score)))

        return composite_score, suggested_length

    def run_from_db(
        self,
        read_fn=None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict:
        """Run cycle detection using data from TimescaleDB.

        Args:
            read_fn: Callable like tsdb.read_ohlcv(symbol, timeframe, start, end).
            start: Start datetime string.
            end: End datetime string.
        """
        if read_fn is None:
            raise ValueError("read_fn is required for database-backed analysis")

        data = {}
        for tf in self.timeframes:
            df = read_fn(self.symbol, tf, start=start, end=end)
            if not df.empty:
                data[tf] = df

        return self.run(data)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert latest results to summary DataFrame."""
        if not self._results:
            return pd.DataFrame()

        rows = []
        for tf, result in self._results.items():
            rows.append({
                "timeframe": tf,
                "dominant_period": result["dominant_period"],
                "dominant_cycle_name": result["dominant_cycle_name"],
                "dominant_power": result["dominant_power"],
                "composite": result["composite"],
                "method": result["method"],
            })

        return pd.DataFrame(rows)

    def write_to_db(self, write_fn=None) -> int:
        """Write results to TimescaleDB dominant_cycles table.

        Args:
            write_fn: Callable that accepts a DataFrame with dominant_cycles columns.

        Returns:
            Number of rows written.
        """
        if write_fn is None or not self._results:
            return 0

        now = datetime.now(timezone.utc)
        rows = []
        for tf, result in self._results.items():
            rows.append({
                "time": now,
                "symbol": self.symbol,
                "timeframe": tf,
                "method": result["method"],
                "period": result["dominant_period"],
                "power": result["dominant_power"],
                "composite": result["composite"],
            })

        df = pd.DataFrame(rows)
        written = write_fn(df)
        logger.info("Wrote %d cycle results to DB", len(rows))
        return written if written is not None else len(rows)
