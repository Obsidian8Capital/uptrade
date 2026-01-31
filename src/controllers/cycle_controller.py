"""Cycle (Spectral Analysis) V2 Controller.

Wraps the :class:`SpectralAnalysis` indicator (Hurst / Goertzel cycle
detection) as a Hummingbot V2 directional-trading controller.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from src.controllers.base_vbt_controller import BaseVBTController, BaseVBTControllerConfig


class CycleControllerConfig(BaseVBTControllerConfig):
    """Configuration for the SpectralAnalysis controller."""

    controller_type: str = "vbt_cycle"
    method: int = 0  # 0 = Hurst, 1 = Goertzel
    bandwidth: float = 0.025
    window_size: int = 618
    scale_factor: float = 100_000.0
    composite_threshold: float = 0.0  # signal fires when composite crosses this


class CycleController(BaseVBTController):
    """Directional controller powered by :class:`SpectralAnalysis`.

    The composite cycle oscillator is compared against
    ``composite_threshold``.  When the composite is above the threshold the
    signal is long (``1``); below is short (``-1``); exactly on the
    threshold yields neutral (``0``).
    """

    def __init__(
        self,
        config: CycleControllerConfig,
        market_data_provider: Optional[Any] = None,
        actions_proposal_timeout: Optional[int] = None,
    ) -> None:
        super().__init__(config, market_data_provider, actions_proposal_timeout)

    def compute_signal(self, df: pd.DataFrame) -> int:
        # Lazy imports — VBT / Numba are heavy
        from src.indicators.spectral import SpectralAnalysis

        # SpectralAnalysis expects a single "source" series (typically hl2)
        if "close" in df.columns:
            close = df["close"].values
        else:
            close = df["Close"].values

        if "high" in df.columns and "low" in df.columns:
            high = df["high"].values
            low = df["low"].values
            source = (high + low) / 2.0  # hl2
        elif "High" in df.columns and "Low" in df.columns:
            high = df["High"].values
            low = df["Low"].values
            source = (high + low) / 2.0
        else:
            source = close

        cfg: CycleControllerConfig = self.config  # type: ignore[assignment]

        result = SpectralAnalysis.run(
            source,
            method=cfg.method,
            bandwidth=cfg.bandwidth,
            window_size=cfg.window_size,
            scale_factor=cfg.scale_factor,
        )

        composite = result.composite.values

        if len(composite) == 0 or np.isnan(composite[-1]):
            return 0

        latest = float(composite[-1])
        if latest > cfg.composite_threshold:
            return 1
        elif latest < cfg.composite_threshold:
            return -1
        return 0
