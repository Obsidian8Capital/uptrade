"""Shared pytest fixtures for UpTrade integration tests.

All fixtures produce deterministic, self-contained data that does NOT
require live services (no DB, no exchange, no API keys).
"""
import sys
from pathlib import Path
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

# Ensure src is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# OHLCV fixtures
# ---------------------------------------------------------------------------

def _make_ohlcv(n_bars: int, seed: int, base_price: float, trend: float = 0.0) -> pd.DataFrame:
    """Generate synthetic OHLCV with proper high >= open/close >= low."""
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="h", tz="UTC")

    close = np.empty(n_bars)
    close[0] = base_price
    for i in range(1, n_bars):
        ret = rng.normal(trend, 0.005)
        close[i] = close[i - 1] * (1.0 + ret)

    open_ = close * (1.0 + rng.normal(0, 0.001, n_bars))
    spread = np.abs(rng.normal(0, 0.003, n_bars)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.uniform(100, 5000, n_bars)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture(scope="session")
def sample_ohlcv_df() -> pd.DataFrame:
    """500 bars BTC-USDT 1h, seed=42, ~38000-45000 range, no strong trend."""
    return _make_ohlcv(500, seed=42, base_price=40000.0, trend=0.0002)


@pytest.fixture(scope="session")
def sample_ohlcv_with_trend() -> pd.DataFrame:
    """200 bars with a clear uptrend."""
    return _make_ohlcv(200, seed=10, base_price=38000.0, trend=0.002)


@pytest.fixture(scope="session")
def sample_ohlcv_with_downtrend() -> pd.DataFrame:
    """200 bars with a clear downtrend."""
    return _make_ohlcv(200, seed=20, base_price=45000.0, trend=-0.002)


@pytest.fixture(scope="session")
def short_ohlcv_df() -> pd.DataFrame:
    """Only 10 bars -- for robustness testing (no crash on tiny data)."""
    return _make_ohlcv(10, seed=99, base_price=41000.0)


# ---------------------------------------------------------------------------
# Signal fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_indicator_signals_df() -> pd.DataFrame:
    """DataFrame with time index and signal/value columns."""
    n = 100
    rng = np.random.RandomState(55)
    dates = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    signals = rng.choice([1, 0, -1], size=n, p=[0.2, 0.6, 0.2])
    values = rng.uniform(-1, 1, n)
    return pd.DataFrame({"signal": signals, "value": values}, index=dates)


# ---------------------------------------------------------------------------
# Mock DB engine / connection
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_db_engine():
    """Mock SQLAlchemy engine that avoids any real DB calls."""
    engine = MagicMock()
    conn = MagicMock()
    # Simulate context-manager behaviour
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return engine


# ---------------------------------------------------------------------------
# Mock Hummingbot API (httpx async)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_hb_api():
    """AsyncMock for httpx.AsyncClient used by BotDeployer."""
    client = AsyncMock()
    # Simulate successful deploy response
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"status": "running", "bot_name": "test_bot"}
    response.headers = {"content-type": "application/json"}
    client.post.return_value = response
    client.get.return_value = response
    return client


# ---------------------------------------------------------------------------
# Bot config fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_bot_config():
    """Valid BotDeploymentConfig constructed in-memory."""
    from src.config.bot_config import BotDeploymentConfig

    return BotDeploymentConfig(
        bot_name="test_sniper_bot",
        indicator={"name": "SniperProX", "params": {"length": 28}},
        market={
            "exchange": "binance_perpetual",
            "pair": "BTC-USDT",
            "timeframe": "1h",
            "candles_max": 300,
        },
        execution={
            "strategy": "directional_trading",
            "leverage": 10,
            "stop_loss": 0.03,
            "take_profit": 0.02,
            "time_limit": 2700,
            "max_executors": 2,
            "cooldown": 300,
            "amount_quote": 500,
            "position_mode": "HEDGE",
        },
        data={"source": "polygon"},
    )
