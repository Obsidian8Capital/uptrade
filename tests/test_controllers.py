"""Controller tests -- validate signal output from V2 controllers.

All controllers compute signals from OHLCV DataFrames; no live market
data provider is needed.
"""
import sys
from pathlib import Path
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.controllers.sniper_controller import SniperController, SniperControllerConfig
from src.controllers.vzo_controller import VZOController, VZOControllerConfig
from src.controllers.cycle_controller import CycleController, CycleControllerConfig
from src.config.deployer import INDICATOR_CONTROLLER_MAP


def _make_controller_config(cls, **overrides):
    """Helper to build a controller config with required base fields."""
    defaults = dict(
        connector_name="binance_perpetual",
        trading_pair="BTC-USDT",
        total_amount_quote=Decimal("500"),
    )
    defaults.update(overrides)
    return cls(**defaults)


# ── SniperController ────────────────────────────────────────────────────

class TestSniperController:

    def test_sniper_controller_returns_valid_signal(self, sample_ohlcv_df: pd.DataFrame):
        """SniperController.compute_signal returns -1, 0, or 1."""
        config = _make_controller_config(SniperControllerConfig, length=28)
        ctrl = SniperController(config=config)
        signal = ctrl.compute_signal(sample_ohlcv_df)
        assert signal in (-1, 0, 1)

    def test_sniper_controller_get_signal_default(self):
        """get_signal returns 0 before any computation."""
        config = _make_controller_config(SniperControllerConfig)
        ctrl = SniperController(config=config)
        assert ctrl.get_signal() == 0


# ── VZOController ───────────────────────────────────────────────────────

class TestVZOController:

    def test_vzo_controller_returns_valid_signal(self, sample_ohlcv_df: pd.DataFrame):
        """VZOController.compute_signal returns -1, 0, or 1."""
        config = _make_controller_config(VZOControllerConfig, vzo_length=14)
        ctrl = VZOController(config=config)
        signal = ctrl.compute_signal(sample_ohlcv_df)
        assert signal in (-1, 0, 1)


# ── CycleController ────────────────────────────────────────────────────

class TestCycleController:

    def test_cycle_controller_returns_valid_signal(self, sample_ohlcv_df: pd.DataFrame):
        """CycleController.compute_signal returns -1, 0, or 1."""
        config = _make_controller_config(CycleControllerConfig, method=0)
        ctrl = CycleController(config=config)
        signal = ctrl.compute_signal(sample_ohlcv_df)
        assert signal in (-1, 0, 1)


# ── Config validation ───────────────────────────────────────────────────

class TestControllerConfigValidation:

    def test_sniper_config_defaults(self):
        """SniperControllerConfig has expected default values."""
        config = _make_controller_config(SniperControllerConfig)
        assert config.controller_type == "vbt_sniper"
        assert config.length == 28
        assert config.ma_type == "Jurik Moving Average"

    def test_vzo_config_defaults(self):
        config = _make_controller_config(VZOControllerConfig)
        assert config.controller_type == "vbt_vzo"
        assert config.vzo_length == 14

    def test_cycle_config_defaults(self):
        config = _make_controller_config(CycleControllerConfig)
        assert config.controller_type == "vbt_cycle"
        assert config.method == 0

    def test_config_requires_connector(self):
        """Missing required field raises validation error."""
        with pytest.raises(Exception):
            SniperControllerConfig(trading_pair="BTC-USDT", total_amount_quote=Decimal("500"))


# ── Controller registry completeness ────────────────────────────────────

class TestControllerRegistry:

    def test_controller_registry_complete(self):
        """INDICATOR_CONTROLLER_MAP covers the three main indicators."""
        assert "SniperProX" in INDICATOR_CONTROLLER_MAP
        assert "VZOProX" in INDICATOR_CONTROLLER_MAP
        assert "SpectralAnalysis" in INDICATOR_CONTROLLER_MAP
        assert INDICATOR_CONTROLLER_MAP["SniperProX"] == "vbt_sniper"
        assert INDICATOR_CONTROLLER_MAP["VZOProX"] == "vbt_vzo"
        assert INDICATOR_CONTROLLER_MAP["SpectralAnalysis"] == "vbt_cycle"
