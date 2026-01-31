"""VZOProX V2 Controller.

Wraps the :class:`VZOProX` indicator (Volume Zone Oscillator with adaptive
MA smoothing) as a Hummingbot V2 directional-trading controller.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from src.controllers.base_vbt_controller import BaseVBTController, BaseVBTControllerConfig


class VZOControllerConfig(BaseVBTControllerConfig):
    """Configuration for the VZOProX controller."""

    controller_type: str = "vbt_vzo"
    vzo_length: int = 14
    ma_type: str = "Jurik Moving Average"
    noise_length: int = 2
    minor_sell_val: float = 40.0
    minor_buy_val: float = -40.0
    minor_major_range: float = 20.0
    zero_cross_filter_range: float = 20.0


class VZOController(BaseVBTController):
    """Directional controller powered by :class:`VZOProX`.

    The latest bar's ``major_buy`` / ``major_sell`` signals determine the
    direction: ``1`` (long), ``-1`` (short), or ``0`` (neutral).
    """

    def __init__(
        self,
        config: VZOControllerConfig,
        market_data_provider: Optional[Any] = None,
        actions_proposal_timeout: Optional[int] = None,
    ) -> None:
        super().__init__(config, market_data_provider, actions_proposal_timeout)

    def compute_signal(self, df: pd.DataFrame) -> int:
        # Lazy imports — VBT / Numba are heavy
        from src.indicators.vzo import VZOProX

        close = df["close"].values if "close" in df.columns else df["Close"].values
        volume = df["volume"].values if "volume" in df.columns else df["Volume"].values

        cfg: VZOControllerConfig = self.config  # type: ignore[assignment]

        result = VZOProX.run(
            close,
            volume,
            vzo_length=cfg.vzo_length,
            ma_type=cfg.ma_type,
            noise_length=cfg.noise_length,
            minor_sell_val=cfg.minor_sell_val,
            minor_buy_val=cfg.minor_buy_val,
            minor_major_range=cfg.minor_major_range,
            zero_cross_filter_range=cfg.zero_cross_filter_range,
        )

        major_buy = result.major_buy.values
        major_sell = result.major_sell.values

        if len(major_buy) > 0 and not np.isnan(major_buy[-1]):
            return 1
        if len(major_sell) > 0 and not np.isnan(major_sell[-1]):
            return -1
        return 0
