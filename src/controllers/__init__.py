"""UpTrade V2 Controller Bridge -- VBT indicators for Hummingbot."""

from src.controllers.base_vbt_controller import (
    BaseVBTController,
    BaseVBTControllerConfig,
    DirectionalTradingControllerConfigBase,
)
from src.controllers.sniper_controller import SniperController, SniperControllerConfig
from src.controllers.vzo_controller import VZOController, VZOControllerConfig
from src.controllers.cycle_controller import CycleController, CycleControllerConfig

CONTROLLER_REGISTRY: dict[str, type[BaseVBTController]] = {
    "vbt_sniper": SniperController,
    "vbt_vzo": VZOController,
    "vbt_cycle": CycleController,
}

__all__ = [
    "BaseVBTController",
    "BaseVBTControllerConfig",
    "DirectionalTradingControllerConfigBase",
    "SniperController",
    "SniperControllerConfig",
    "VZOController",
    "VZOControllerConfig",
    "CycleController",
    "CycleControllerConfig",
    "CONTROLLER_REGISTRY",
]
