"""Enhanced signal combiner with AND/OR/WEIGHTED/CONFIRM modes."""
from enum import Enum
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

from src.logging_config import get_logger

logger = get_logger("signal_combiner")


class CombineMode(str, Enum):
    """Signal combination modes."""
    AND = "and"
    OR = "or"
    WEIGHTED = "weighted"
    CONFIRM = "confirm"


class IndicatorSignalConfig(BaseModel):
    """Configuration for a single indicator's signal contribution."""
    name: str
    weight: float = 1.0
    role: str = "secondary"  # "primary" or "secondary" for CONFIRM mode
    signal_source: str = "major"  # "major", "minor", or "composite"


class SignalCombinerConfig(BaseModel):
    """Configuration for the signal combiner."""
    mode: CombineMode = CombineMode.AND
    indicators: list[IndicatorSignalConfig] = Field(default_factory=list)
    weighted_threshold: float = 0.5
    confirm_window: int = 3


class SignalCombiner:
    """Combines multiple indicator signals into a single actionable signal array."""

    def __init__(
        self,
        config: Optional[SignalCombinerConfig] = None,
        mode: str = "and",
    ):
        """Initialize the signal combiner.

        Args:
            config: Full combiner configuration.
            mode: Simple mode string (used if config is None).
        """
        if config is not None:
            self.config = config
        else:
            self.config = SignalCombinerConfig(mode=CombineMode(mode))

    def combine(self, signals: dict[str, np.ndarray]) -> np.ndarray:
        """Combine multiple indicator signals into one.

        Args:
            signals: Dict of {indicator_name: signal_array} where each array
                     contains integers (1=long, 0=neutral, -1=short).

        Returns:
            Combined signal array with values in {-1, 0, 1}.
        """
        if not signals:
            raise ValueError("No signals provided")

        # Validate all arrays same length
        lengths = {name: len(arr) for name, arr in signals.items()}
        unique_lengths = set(lengths.values())
        if len(unique_lengths) > 1:
            raise ValueError(f"Signal arrays have different lengths: {lengths}")

        mode = self.config.mode
        if mode == CombineMode.AND:
            return self._combine_and(signals)
        elif mode == CombineMode.OR:
            return self._combine_or(signals)
        elif mode == CombineMode.WEIGHTED:
            return self._combine_weighted(signals)
        elif mode == CombineMode.CONFIRM:
            return self._combine_confirm(signals)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _combine_and(self, signals: dict[str, np.ndarray]) -> np.ndarray:
        """AND mode: all indicators must agree."""
        arrays = list(signals.values())
        matrix = np.stack(arrays, axis=0)  # (n_indicators, n_bars)

        all_long = np.all(matrix == 1, axis=0)
        all_short = np.all(matrix == -1, axis=0)

        result = np.where(all_long, 1, np.where(all_short, -1, 0))
        return result.astype(np.int64)

    def _combine_or(self, signals: dict[str, np.ndarray]) -> np.ndarray:
        """OR mode: any non-zero triggers, majority vote on conflicts."""
        arrays = list(signals.values())
        matrix = np.stack(arrays, axis=0)

        # Count longs and shorts per bar
        long_count = np.sum(matrix == 1, axis=0)
        short_count = np.sum(matrix == -1, axis=0)

        # Any long and no short -> long
        # Any short and no long -> short
        # Both -> majority vote (sign of sum)
        # Neither -> neutral
        has_long = long_count > 0
        has_short = short_count > 0

        result = np.zeros(matrix.shape[1], dtype=np.int64)
        result[has_long & ~has_short] = 1
        result[has_short & ~has_long] = -1

        # Conflicts: majority vote
        conflict = has_long & has_short
        if np.any(conflict):
            vote_sum = np.sum(matrix[:, conflict], axis=0)
            result[conflict] = np.sign(vote_sum).astype(np.int64)

        return result

    def _combine_weighted(self, signals: dict[str, np.ndarray]) -> np.ndarray:
        """WEIGHTED mode: weighted sum compared to threshold."""
        # Build weight map from config
        weight_map = {}
        for ind_config in self.config.indicators:
            weight_map[ind_config.name] = ind_config.weight

        n_bars = len(next(iter(signals.values())))
        weighted_sum = np.zeros(n_bars, dtype=np.float64)
        total_weight = 0.0

        for name, arr in signals.items():
            w = weight_map.get(name, 1.0)
            weighted_sum += arr.astype(np.float64) * w
            total_weight += w

        if total_weight > 0:
            normalized = weighted_sum / total_weight
        else:
            normalized = weighted_sum

        threshold = self.config.weighted_threshold
        result = np.where(
            normalized >= threshold, 1,
            np.where(normalized <= -threshold, -1, 0)
        )
        return result.astype(np.int64)

    def _combine_confirm(self, signals: dict[str, np.ndarray]) -> np.ndarray:
        """CONFIRM mode: primary signals, secondary confirms within window."""
        # Identify primary and secondary indicators
        primary_names = [c.name for c in self.config.indicators if c.role == "primary"]
        secondary_names = [c.name for c in self.config.indicators if c.role == "secondary"]

        if not primary_names:
            logger.warning("No primary indicator defined for CONFIRM mode, falling back to AND")
            return self._combine_and(signals)

        # Get primary signal (use first primary if multiple)
        primary_name = primary_names[0]
        if primary_name not in signals:
            logger.warning("Primary indicator %s not in signals, falling back to AND", primary_name)
            return self._combine_and(signals)

        primary = signals[primary_name]
        n_bars = len(primary)
        window = self.config.confirm_window

        # Build secondary matrix
        sec_arrays = [signals[name] for name in secondary_names if name in signals]
        if not sec_arrays:
            return primary.copy().astype(np.int64)

        sec_matrix = np.stack(sec_arrays, axis=0)

        result = np.zeros(n_bars, dtype=np.int64)
        for i in range(n_bars):
            if primary[i] == 0:
                continue

            direction = primary[i]
            # Look within window (forward and backward)
            start = max(0, i - window)
            end = min(n_bars, i + window + 1)

            # Check if any secondary confirms in the window
            window_slice = sec_matrix[:, start:end]
            if np.any(window_slice == direction):
                result[i] = direction

        return result

    @staticmethod
    def convert_indicator_output(indicator_result, signal_source: str = "major") -> np.ndarray:
        """Convert VBT IndicatorFactory output to integer signal array.

        Args:
            indicator_result: VBT indicator result object.
            signal_source: "major", "minor", or "composite".

        Returns:
            Integer array with values in {-1, 0, 1}.
        """
        if signal_source == "major":
            buy = ~np.isnan(np.asarray(indicator_result.major_buy, dtype=np.float64))
            sell = ~np.isnan(np.asarray(indicator_result.major_sell, dtype=np.float64))
            return np.where(buy, 1, np.where(sell, -1, 0)).astype(np.int64)
        elif signal_source == "minor":
            buy = ~np.isnan(np.asarray(indicator_result.minor_buy, dtype=np.float64))
            sell = ~np.isnan(np.asarray(indicator_result.minor_sell, dtype=np.float64))
            return np.where(buy, 1, np.where(sell, -1, 0)).astype(np.int64)
        elif signal_source == "composite":
            composite = np.asarray(indicator_result.composite, dtype=np.float64)
            return np.where(composite > 0, 1, np.where(composite < 0, -1, 0)).astype(np.int64)
        else:
            raise ValueError(f"Unknown signal_source: {signal_source}")

    @classmethod
    def from_yaml(cls, config_dict: dict) -> "SignalCombiner":
        """Create combiner from YAML-style config dict."""
        config = SignalCombinerConfig(**config_dict)
        return cls(config=config)

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return self.config.model_dump()
