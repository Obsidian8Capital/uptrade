"""Shared enums for UpTrade platform."""
from enum import Enum, IntEnum


class IndicatorType(str, Enum):
    """Supported indicator types."""
    SNIPER = "SniperProX"
    VZO = "VZOProX"
    SPECTRAL = "SpectralAnalysis"
    UNIVERSAL_MA = "UniversalMA"
    CELESTIAL = "CelestialChannels"
    CUSTOM = "Custom"


class ExchangeType(str, Enum):
    """Exchange venue types."""
    CEX = "cex"
    DEX = "dex"


class SignalDirection(IntEnum):
    """Trading signal direction."""
    SHORT = -1
    NEUTRAL = 0
    LONG = 1


class TimeframeEnum(str, Enum):
    """Supported trading timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class PositionMode(str, Enum):
    """Position mode for futures trading."""
    ONEWAY = "ONEWAY"
    HEDGE = "HEDGE"


class DataSource(str, Enum):
    """Data source for market data."""
    POLYGON = "polygon"
    EXCHANGE = "exchange"
