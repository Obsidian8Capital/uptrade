"""Smoke tests for all UpTrade indicators.

Every test runs on synthetic OHLCV data (conftest fixtures) with VBT Pro
IndicatorFactory objects, validating output shape and no-crash behaviour.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.indicators.sniper import SniperProX
from src.indicators.vzo import VZOProX
from src.indicators.spectral import SpectralAnalysis
from src.indicators.ma_library import UniversalMA
from src.signals.combiner import SignalCombiner, SignalCombinerConfig, CombineMode, IndicatorSignalConfig


# ── SniperProX ──────────────────────────────────────────────────────────

class TestSniperProX:

    def test_sniper_produces_valid_output(self, sample_ohlcv_df: pd.DataFrame):
        """SniperProX.run returns expected output names with matching length."""
        df = sample_ohlcv_df
        result = SniperProX.run(
            df["close"], df["high"], df["low"], df["volume"],
            length=28,
        )
        assert hasattr(result, "f3")
        assert hasattr(result, "major_buy")
        assert hasattr(result, "major_sell")
        assert len(result.f3) == len(df)

    def test_sniper_with_short_data(self, short_ohlcv_df: pd.DataFrame):
        """SniperProX should not crash on very short data (10 bars)."""
        df = short_ohlcv_df
        result = SniperProX.run(
            df["close"], df["high"], df["low"], df["volume"],
            length=28,
        )
        assert len(result.f3) == len(df)


# ── VZOProX ─────────────────────────────────────────────────────────────

class TestVZOProX:

    def test_vzo_produces_valid_output(self, sample_ohlcv_df: pd.DataFrame):
        """VZOProX.run returns vzo, major_buy, major_sell with correct length."""
        df = sample_ohlcv_df
        result = VZOProX.run(df["close"], df["volume"], vzo_length=14)
        assert hasattr(result, "vzo")
        assert hasattr(result, "major_buy")
        assert hasattr(result, "major_sell")
        assert len(result.vzo) == len(df)

    def test_vzo_with_short_data(self, short_ohlcv_df: pd.DataFrame):
        """VZOProX should not crash on 10 bars."""
        df = short_ohlcv_df
        result = VZOProX.run(df["close"], df["volume"], vzo_length=14)
        assert len(result.vzo) == len(df)


# ── SpectralAnalysis ────────────────────────────────────────────────────

class TestSpectralAnalysis:

    def test_spectral_produces_valid_output(self, sample_ohlcv_df: pd.DataFrame):
        """SpectralAnalysis.run returns composite output."""
        df = sample_ohlcv_df
        source = (df["high"] + df["low"]) / 2.0
        result = SpectralAnalysis.run(source, method=0)
        assert hasattr(result, "composite")
        assert len(result.composite) == len(df)

    def test_spectral_goertzel_method(self, sample_ohlcv_df: pd.DataFrame):
        """Goertzel method (method=1) also produces valid output."""
        df = sample_ohlcv_df
        source = (df["high"] + df["low"]) / 2.0
        result = SpectralAnalysis.run(source, method=1)
        assert len(result.composite) == len(df)

    def test_spectral_with_short_data(self, short_ohlcv_df: pd.DataFrame):
        """SpectralAnalysis should not crash on 10 bars."""
        df = short_ohlcv_df
        source = (df["high"] + df["low"]) / 2.0
        result = SpectralAnalysis.run(source, method=0)
        assert len(result.composite) == len(df)


# ── UniversalMA ─────────────────────────────────────────────────────────

class TestUniversalMA:

    MA_TYPES_TO_TEST = [
        "Simple Moving Average",
        "Exponential Moving Average",
        "Jurik Moving Average",
        "Hull Moving Average",
        "Triangular Moving Average",
    ]

    @pytest.mark.parametrize("ma_type", MA_TYPES_TO_TEST)
    def test_universal_ma_type(self, sample_ohlcv_df: pd.DataFrame, ma_type: str):
        """UniversalMA.run produces output for each MA type without crashing."""
        df = sample_ohlcv_df
        result = UniversalMA.run(df["close"], window=14, ma_type=ma_type)
        assert hasattr(result, "ma")
        assert len(result.ma) == len(df)


# ── SignalCombiner ──────────────────────────────────────────────────────

class TestSignalCombiner:

    def test_combiner_and_mode(self):
        """AND mode: all must agree for non-zero output."""
        signals = {
            "a": np.array([1, 1, -1, 0, 1]),
            "b": np.array([1, -1, -1, 0, 1]),
        }
        combiner = SignalCombiner(mode="and")
        result = combiner.combine(signals)
        expected = np.array([1, 0, -1, 0, 1])
        np.testing.assert_array_equal(result, expected)

    def test_combiner_or_mode(self):
        """OR mode: any non-zero triggers, majority vote on conflicts."""
        signals = {
            "a": np.array([1, 0, -1, 0]),
            "b": np.array([0, 0, -1, 0]),
        }
        combiner = SignalCombiner(mode="or")
        result = combiner.combine(signals)
        assert result[0] == 1   # a=1, b=0 -> long
        assert result[1] == 0   # both neutral
        assert result[2] == -1  # both short
        assert result[3] == 0   # both neutral

    def test_combiner_weighted_mode(self):
        """WEIGHTED mode: weighted sum vs threshold."""
        config = SignalCombinerConfig(
            mode=CombineMode.WEIGHTED,
            indicators=[
                IndicatorSignalConfig(name="a", weight=2.0),
                IndicatorSignalConfig(name="b", weight=1.0),
            ],
            weighted_threshold=0.5,
        )
        signals = {
            "a": np.array([1, -1, 1, 0]),
            "b": np.array([1, 1, -1, 0]),
        }
        combiner = SignalCombiner(config=config)
        result = combiner.combine(signals)
        # Bar 0: (2*1 + 1*1)/3 = 1.0 >= 0.5 -> 1
        assert result[0] == 1
        # Bar 3: 0 -> 0
        assert result[3] == 0

    def test_combiner_empty_signals_raises(self):
        """Combine raises ValueError on empty input."""
        combiner = SignalCombiner(mode="and")
        with pytest.raises(ValueError, match="No signals"):
            combiner.combine({})

    def test_combiner_mismatched_lengths_raises(self):
        """Combine raises ValueError when signal arrays differ in length."""
        signals = {
            "a": np.array([1, 0]),
            "b": np.array([1, 0, -1]),
        }
        combiner = SignalCombiner(mode="and")
        with pytest.raises(ValueError, match="different lengths"):
            combiner.combine(signals)

    def test_convert_indicator_output_major(self, sample_ohlcv_df: pd.DataFrame):
        """convert_indicator_output extracts major buy/sell into int array."""
        df = sample_ohlcv_df
        result = SniperProX.run(
            df["close"], df["high"], df["low"], df["volume"],
            length=28,
        )
        sig = SignalCombiner.convert_indicator_output(result, signal_source="major")
        assert sig.dtype == np.int64
        assert set(np.unique(sig)).issubset({-1, 0, 1})
        assert len(sig) == len(df)
