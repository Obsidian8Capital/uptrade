"""Shared type definitions for UpTrade platform."""
from typing import NamedTuple, TypedDict
from datetime import datetime

import numpy as np
import numpy.typing as npt
import pandas as pd


# Type aliases
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]
Series = pd.Series
DataFrame = pd.DataFrame


class OHLCVData(TypedDict):
    """OHLCV market data structure."""
    time: list[datetime]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]
    vwap: list[float] | None
    trade_count: list[int] | None


class SignalResult(NamedTuple):
    """Result from indicator signal generation."""
    signal: int  # -1, 0, 1
    value: float  # raw indicator value
    timestamp: datetime
