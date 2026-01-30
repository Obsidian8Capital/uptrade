"""Pydantic models for bot deployment YAML configuration."""
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from src.enums import (
    DataSource,
    IndicatorType,
    PositionMode,
    TimeframeEnum,
)


class IndicatorConfig(BaseModel):
    """Indicator configuration."""
    name: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_indicator_name(cls, v: str) -> str:
        valid_names = {e.value for e in IndicatorType}
        if v not in valid_names and v not in {e.name for e in IndicatorType}:
            # Allow custom indicator names
            pass
        return v


class MarketConfig(BaseModel):
    """Market/exchange configuration."""
    exchange: str
    pair: str
    timeframe: TimeframeEnum
    candles_max: int = Field(default=300, ge=50, le=5000)


class ExecutionConfig(BaseModel):
    """Execution/risk parameters."""
    strategy: str = Field(default="directional_trading")
    leverage: int = Field(default=1, ge=1, le=125)
    stop_loss: float = Field(default=0.03, gt=0, lt=1)
    take_profit: float = Field(default=0.02, gt=0, lt=1)
    time_limit: int = Field(default=2700, ge=60)
    max_executors: int = Field(default=2, ge=1, le=10)
    cooldown: int = Field(default=300, ge=0)
    amount_quote: float = Field(default=100, gt=0)
    position_mode: PositionMode = Field(default=PositionMode.ONEWAY)


class DataConfig(BaseModel):
    """Data source configuration."""
    source: DataSource = Field(default=DataSource.POLYGON)
    symbol_override: Optional[str] = None


class BotDeploymentConfig(BaseModel):
    """Complete bot deployment configuration."""
    bot_name: str
    indicator: IndicatorConfig
    market: MarketConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    data: DataConfig = Field(default_factory=DataConfig)

    @field_validator("bot_name")
    @classmethod
    def validate_bot_name(cls, v: str) -> str:
        if not v or len(v) > 100:
            raise ValueError("bot_name must be 1-100 characters")
        return v


def load_bot_config(path: str) -> BotDeploymentConfig:
    """Load and validate a bot deployment config from YAML."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return BotDeploymentConfig(**data)


def load_all_configs(directory: str) -> list[BotDeploymentConfig]:
    """Load all YAML configs from a directory."""
    config_dir = Path(directory)
    if not config_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")
    configs = []
    for path in sorted(config_dir.glob("*.yml")):
        configs.append(load_bot_config(str(path)))
    for path in sorted(config_dir.glob("*.yaml")):
        configs.append(load_bot_config(str(path)))
    return configs
