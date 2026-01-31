"""Base VBT Controller for Hummingbot V2 DirectionalTrading integration.

Provides standalone base classes that mirror Hummingbot's
``DirectionalTradingControllerConfigBase`` / controller interface so the
package can be developed and tested without a Hummingbot installation.
"""

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Config hierarchy
# ---------------------------------------------------------------------------

class DirectionalTradingControllerConfigBase(BaseModel):
    """Mirrors Hummingbot's DirectionalTradingControllerConfigBase.

    Only the fields needed for directional-trading strategies are included;
    extend as required when more Hummingbot features are integrated.
    """

    controller_type: str
    connector_name: str
    trading_pair: str
    total_amount_quote: Decimal
    max_executors_per_side: int = 1
    cooldown_time: int = 300
    leverage: int = 1
    stop_loss: Decimal = Decimal("0.03")
    take_profit: Decimal = Decimal("0.02")
    time_limit: int = 2700


class BaseVBTControllerConfig(DirectionalTradingControllerConfigBase):
    """Extended config adding VBT-specific fields."""

    controller_type: str = "vbt_base"
    candles_max: int = 300
    timeframe: str = "1h"


# ---------------------------------------------------------------------------
# Controller base
# ---------------------------------------------------------------------------

class BaseVBTController(ABC):
    """Base class for VBT-powered Hummingbot V2 controllers.

    Sub-classes must implement :meth:`compute_signal` which receives an
    OHLCV ``DataFrame`` and returns ``1`` (long), ``-1`` (short), or
    ``0`` (neutral).
    """

    def __init__(
        self,
        config: BaseVBTControllerConfig,
        market_data_provider: Optional[Any] = None,
        actions_proposal_timeout: Optional[int] = None,
    ) -> None:
        self.config = config
        self.market_data_provider = market_data_provider
        self._current_signal: int = 0
        self.processed_data: dict[str, Any] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Data pipeline
    # ------------------------------------------------------------------

    async def update_processed_data(self) -> None:
        """Fetch latest candles and recompute the signal."""

        if self.market_data_provider is not None:
            candles = self.market_data_provider.get_candles(
                connector=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                interval=self.config.timeframe,
                max_records=self.config.candles_max,
            )
            df = self._candles_to_dataframe(candles)
        else:
            df = pd.DataFrame()

        if not df.empty:
            try:
                self._current_signal = self.compute_signal(df)
            except Exception as e:
                self.logger.error("Signal computation failed: %s", e)
                self._current_signal = 0

        self.processed_data["signal"] = self._current_signal

    # ------------------------------------------------------------------
    # Signal interface
    # ------------------------------------------------------------------

    @abstractmethod
    def compute_signal(self, df: pd.DataFrame) -> int:
        """Compute trading signal from OHLCV data.

        Returns
        -------
        int
            ``1`` for long, ``-1`` for short, ``0`` for neutral.
        """
        ...

    def get_signal(self) -> int:
        """Return the last computed signal value."""
        return self._current_signal

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _candles_to_dataframe(candles: Any) -> pd.DataFrame:
        """Convert various candle representations to a ``DataFrame``."""

        if isinstance(candles, pd.DataFrame):
            return candles

        if isinstance(candles, (list, np.ndarray)):
            if len(candles) == 0:
                return pd.DataFrame()
            columns = ["timestamp", "open", "high", "low", "close", "volume"]
            first_row = candles[0]
            df = pd.DataFrame(
                candles,
                columns=columns[: len(first_row)] if first_row is not None else columns,
            )
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
            return df

        return pd.DataFrame()
