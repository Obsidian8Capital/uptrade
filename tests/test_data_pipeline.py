"""Data pipeline tests -- all DB/API calls are mocked."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
import yaml

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.config.bot_config import BotDeploymentConfig, load_bot_config


# ── TSDB write_ohlcv formatting ────────────────────────────────────────

class TestTSDBWriter:

    @patch("src.data.tsdb.get_connection")
    def test_write_ohlcv_formats_data(self, mock_conn_ctx, sample_ohlcv_df: pd.DataFrame):
        """write_ohlcv should prepare rows and call execute with upsert SQL."""
        from src.data.tsdb import write_ohlcv

        conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        rows = write_ohlcv(sample_ohlcv_df, symbol="X:BTCUSD", timeframe="1h")
        assert rows == len(sample_ohlcv_df)
        assert conn.execute.called

    @patch("src.data.tsdb.get_connection")
    def test_write_ohlcv_empty_df(self, mock_conn_ctx):
        """write_ohlcv on empty DataFrame returns 0 without DB calls."""
        from src.data.tsdb import write_ohlcv

        rows = write_ohlcv(pd.DataFrame(), symbol="X:BTCUSD", timeframe="1h")
        assert rows == 0
        mock_conn_ctx.assert_not_called()


# ── TSDB read_ohlcv ────────────────────────────────────────────────────

class TestTSDBReader:

    @patch("src.data.tsdb.get_engine")
    def test_read_ohlcv_returns_dataframe(self, mock_engine, sample_ohlcv_df: pd.DataFrame):
        """read_ohlcv returns VBT-compatible DataFrame with capitalized columns."""
        from src.data.tsdb import read_ohlcv

        # Build a result that pd.read_sql would return
        mock_df = sample_ohlcv_df.copy()
        mock_df.index.name = "time"
        mock_df = mock_df.reset_index()

        with patch("src.data.tsdb.pd.read_sql", return_value=mock_df):
            result = read_ohlcv("X:BTCUSD", "1h")

        assert isinstance(result, pd.DataFrame)
        # Columns should be capitalized for VBT
        for col in ("Open", "High", "Low", "Close", "Volume"):
            assert col in result.columns

    @patch("src.data.tsdb.get_engine")
    def test_read_ohlcv_empty(self, mock_engine):
        """read_ohlcv returns empty DF when no data in DB."""
        from src.data.tsdb import read_ohlcv

        with patch("src.data.tsdb.pd.read_sql", return_value=pd.DataFrame()):
            result = read_ohlcv("NOSYMBOL", "1h")

        assert result.empty


# ── Data Updater (mock Polygon client) ─────────────────────────────────

class TestDataUpdater:

    @patch("src.data.updater.PolygonClient")
    @patch("src.data.updater.write_ohlcv")
    @patch("src.data.updater.get_latest_timestamp", return_value=None)
    def test_data_updater_calls_polygon(
        self, mock_latest, mock_write, mock_polygon_cls
    ):
        """DataUpdaterService.startup_backfill calls PolygonClient.incremental_update."""
        from src.data.updater import DataUpdaterService

        mock_client = MagicMock()
        mock_client.incremental_update.return_value = pd.DataFrame({"close": [1, 2]})
        mock_polygon_cls.return_value = mock_client

        service = DataUpdaterService(
            symbols=["X:BTCUSD"],
            timeframes=["1h"],
        )
        # Override the client with our mock
        service.client = mock_client

        service.startup_backfill()
        mock_client.incremental_update.assert_called_once()


# ── Bot config YAML loading ────────────────────────────────────────────

class TestBotConfigYAML:

    def test_bot_config_loads_yaml(self, tmp_path: Path):
        """load_bot_config parses a valid YAML file into BotDeploymentConfig."""
        config_data = {
            "bot_name": "test_bot",
            "indicator": {"name": "SniperProX", "params": {"length": 28}},
            "market": {
                "exchange": "binance_perpetual",
                "pair": "BTC-USDT",
                "timeframe": "1h",
                "candles_max": 300,
            },
            "execution": {
                "strategy": "directional_trading",
                "leverage": 10,
                "stop_loss": 0.03,
                "take_profit": 0.02,
            },
        }
        yaml_path = tmp_path / "test_bot.yml"
        yaml_path.write_text(yaml.dump(config_data))

        config = load_bot_config(str(yaml_path))
        assert isinstance(config, BotDeploymentConfig)
        assert config.bot_name == "test_bot"
        assert config.indicator.name == "SniperProX"
        assert config.market.pair == "BTC-USDT"

    def test_bot_config_rejects_invalid_yaml(self, tmp_path: Path):
        """load_bot_config raises on missing required fields."""
        bad_data = {"bot_name": "x"}  # missing 'indicator' and 'market'
        yaml_path = tmp_path / "bad.yml"
        yaml_path.write_text(yaml.dump(bad_data))

        with pytest.raises(Exception):
            load_bot_config(str(yaml_path))

    def test_bot_config_file_not_found(self):
        """load_bot_config raises FileNotFoundError for nonexistent path."""
        with pytest.raises(FileNotFoundError):
            load_bot_config("/nonexistent/path.yml")


# ── Signal write / read roundtrip (mocked) ─────────────────────────────

class TestSignalRoundtrip:

    @patch("src.data.tsdb.get_connection")
    @patch("src.data.tsdb.get_engine")
    def test_indicator_signals_write_read(
        self,
        mock_engine,
        mock_conn_ctx,
        sample_indicator_signals_df: pd.DataFrame,
    ):
        """write_signals formats data, read_signals returns expected shape."""
        from src.data.tsdb import write_signals, read_signals

        conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        rows = write_signals(
            sample_indicator_signals_df,
            symbol="X:BTCUSD",
            timeframe="1h",
            indicator="SniperProX",
            params={"length": 28},
        )
        assert rows == len(sample_indicator_signals_df)

        # read_signals with mocked pd.read_sql
        mock_read_df = sample_indicator_signals_df.copy()
        mock_read_df.index.name = "time"
        mock_read_df = mock_read_df.reset_index()

        with patch("src.data.tsdb.pd.read_sql", return_value=mock_read_df):
            read_df = read_signals("X:BTCUSD", "1h", "SniperProX")

        assert isinstance(read_df, pd.DataFrame)
        assert "signal" in read_df.columns
