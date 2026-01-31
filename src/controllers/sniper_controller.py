"""SniperProX V2 Controller.

Wraps the :class:`SniperProX` indicator (Fisher-transform oscillator with
adaptive MA & DMI filtering) as a Hummingbot V2 directional-trading
controller.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from src.controllers.base_vbt_controller import BaseVBTController, BaseVBTControllerConfig


class SniperControllerConfig(BaseVBTControllerConfig):
    """Configuration for the SniperProX controller."""

    controller_type: str = "vbt_sniper"
    length: int = 28
    ma_type: str = "Jurik Moving Average"
    overbought_oversold: float = 1.386
    trail_threshold: float = 0.986
    dmi_len: int = 14
    adx_threshold: float = 20.0


class SniperController(BaseVBTController):
    """Directional controller powered by :class:`SniperProX`.

    The latest bar's ``major_buy`` / ``major_sell`` signals determine the
    direction: ``1`` (long), ``-1`` (short), or ``0`` (neutral).
    """

    def __init__(
        self,
        config: SniperControllerConfig,
        market_data_provider: Optional[Any] = None,
        actions_proposal_timeout: Optional[int] = None,
    ) -> None:
        super().__init__(config, market_data_provider, actions_proposal_timeout)

    def compute_signal(self, df: pd.DataFrame) -> int:
        # Lazy imports — VBT / Numba are heavy
        from src.indicators.sniper import SniperProX
        from src.indicators.nb.ma_library_nb import MA_TYPE_NAMES

        close = df["close"].values if "close" in df.columns else df["Close"].values
        high = df["high"].values if "high" in df.columns else df["High"].values
        low = df["low"].values if "low" in df.columns else df["Low"].values
        volume = df["volume"].values if "volume" in df.columns else df["Volume"].values

        # Resolve MA type name to integer code
        cfg: SniperControllerConfig = self.config  # type: ignore[assignment]
        ma_type_idx: int = 0
        for idx, name in MA_TYPE_NAMES.items():
            if name == cfg.ma_type:
                ma_type_idx = idx
                break

        result = SniperProX.run(
            close,
            high,
            low,
            volume,
            length=cfg.length,
            ma_type=ma_type_idx,
            overbought_oversold=cfg.overbought_oversold,
            trail_threshold=cfg.trail_threshold,
            dmi_len=cfg.dmi_len,
            adx_thresh=cfg.adx_threshold,
        )

        major_buy = result.major_buy.values
        major_sell = result.major_sell.values

        if len(major_buy) > 0 and not np.isnan(major_buy[-1]):
            return 1
        if len(major_sell) > 0 and not np.isnan(major_sell[-1]):
            return -1
        return 0
