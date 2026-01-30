"""End-to-end integration tests.

These tests validate the full UpTrade pipeline:
  data -> indicators -> signals -> controllers -> deployer
All external services (DB, API) are mocked.
"""
import sys
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock

import numpy as np
import pandas as pd
import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.indicators.sniper import SniperProX
from src.indicators.vzo import VZOProX
from src.indicators.spectral import SpectralAnalysis
from src.signals.combiner import SignalCombiner, SignalCombinerConfig, CombineMode, IndicatorSignalConfig
from src.controllers.sniper_controller import SniperController, SniperControllerConfig
from src.controllers.cycle_controller import CycleController, CycleControllerConfig
from src.config.deployer import BotDeployer, INDICATOR_CONTROLLER_MAP


def _ctrl_config(cls, **kw):
    defaults = dict(
        connector_name="binance_perpetual",
        trading_pair="BTC-USDT",
        total_amount_quote=Decimal("500"),
    )
    defaults.update(kw)
    return cls(**defaults)


# ── Full pipeline: data -> indicators -> combiner -> signal ─────────────

class TestFullPipelineDataToSignal:

    def test_full_pipeline_data_to_signal(self, sample_ohlcv_df: pd.DataFrame):
        """OHLCV -> SniperProX + VZOProX -> combiner -> actionable signal."""
        df = sample_ohlcv_df

        # Run indicators
        sniper_result = SniperProX.run(
            df["close"], df["high"], df["low"], df["volume"],
            length=28,
        )
        vzo_result = VZOProX.run(df["close"], df["volume"], vzo_length=14)

        # Convert to integer signal arrays
        sniper_sig = SignalCombiner.convert_indicator_output(sniper_result, "major")
        vzo_sig = SignalCombiner.convert_indicator_output(vzo_result, "major")

        assert sniper_sig.dtype == np.int64
        assert vzo_sig.dtype == np.int64
        assert len(sniper_sig) == len(df)

        # Combine with AND mode
        combiner = SignalCombiner(mode="and")
        combined = combiner.combine({"sniper": sniper_sig, "vzo": vzo_sig})
        assert combined.dtype == np.int64
        assert set(np.unique(combined)).issubset({-1, 0, 1})


# ── Config -> controller -> signal ──────────────────────────────────────

class TestFullPipelineConfigToController:

    def test_full_pipeline_config_to_controller_output(self, sample_ohlcv_df: pd.DataFrame):
        """BotDeploymentConfig params -> SniperController -> signal."""
        config = _ctrl_config(SniperControllerConfig, length=28)
        ctrl = SniperController(config=config)
        signal = ctrl.compute_signal(sample_ohlcv_df)
        assert signal in (-1, 0, 1)

    def test_cycle_controller_from_config(self, sample_ohlcv_df: pd.DataFrame):
        """CycleControllerConfig -> CycleController -> signal."""
        config = _ctrl_config(CycleControllerConfig, method=0)
        ctrl = CycleController(config=config)
        signal = ctrl.compute_signal(sample_ohlcv_df)
        assert signal in (-1, 0, 1)


# ── Deploy flow (mocked API) ───────────────────────────────────────────

class TestDeployFlowMocked:

    @pytest.mark.asyncio
    async def test_deploy_flow_mocked(self, sample_bot_config, mock_hb_api):
        """BotDeployer.deploy_bot sends correct payload via mocked httpx."""
        deployer = BotDeployer(
            api_url="http://localhost:8000",
            username="admin",
            password="admin",
        )
        # Replace the internal httpx client with our mock
        deployer._client = mock_hb_api

        result = await deployer.deploy_bot(sample_bot_config)
        assert result["status"] == "running"

        # Verify the POST was called with deploy endpoint
        mock_hb_api.post.assert_called_once()
        call_args = mock_hb_api.post.call_args
        assert "/bot-orchestration/deploy-v2-script" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["bot_name"] == "test_sniper_bot"
        assert payload["controller_config"]["controller_type"] == "vbt_sniper"


# ── Indicator -> TSDB roundtrip (mocked) ────────────────────────────────

class TestIndicatorTSDBRoundtrip:

    @patch("src.data.tsdb.get_connection")
    @patch("src.data.tsdb.get_engine")
    def test_indicator_to_tsdb_roundtrip(
        self, mock_engine, mock_conn_ctx, sample_ohlcv_df: pd.DataFrame
    ):
        """Run indicator, write signals to mock DB, read them back."""
        from src.data.tsdb import write_signals, read_signals

        conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        df = sample_ohlcv_df
        result = SniperProX.run(
            df["close"], df["high"], df["low"], df["volume"],
            length=28,
        )
        sig_array = SignalCombiner.convert_indicator_output(result, "major")

        # Build signals DataFrame with expected schema
        sig_df = pd.DataFrame(
            {"signal": sig_array, "value": result.f3.values},
            index=df.index,
        )
        sig_df.index.name = "time"

        rows = write_signals(
            sig_df,
            symbol="X:BTCUSD",
            timeframe="1h",
            indicator="SniperProX",
            params={"length": 28},
        )
        assert rows == len(df)

        # Simulate reading back
        mock_read_df = sig_df.reset_index()
        with patch("src.data.tsdb.pd.read_sql", return_value=mock_read_df):
            read_df = read_signals("X:BTCUSD", "1h", "SniperProX")

        assert "signal" in read_df.columns
        assert len(read_df) == len(df)


# ── Spectral -> dashboard data format ───────────────────────────────────

class TestCycleDetectorToDashboard:

    def test_cycle_detector_to_dashboard_data(self, sample_ohlcv_df: pd.DataFrame):
        """SpectralAnalysis composite can be converted to dashboard-friendly format."""
        df = sample_ohlcv_df
        source = (df["high"] + df["low"]) / 2.0
        result = SpectralAnalysis.run(source, method=0)

        composite = result.composite
        assert len(composite) == len(df)

        # Build dashboard-style dict with dominant cycle info
        composite_values = composite.values
        last_value = float(composite_values[-1]) if not np.isnan(composite_values[-1]) else 0.0

        dashboard_data = {
            "composite_latest": last_value,
            "composite_mean": float(np.nanmean(composite_values)),
            "composite_std": float(np.nanstd(composite_values)),
            "direction": "bullish" if last_value > 0 else ("bearish" if last_value < 0 else "neutral"),
            "n_bars": len(composite_values),
        }
        assert "composite_latest" in dashboard_data
        assert dashboard_data["n_bars"] == len(df)
        assert dashboard_data["direction"] in ("bullish", "bearish", "neutral")
