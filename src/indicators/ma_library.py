"""UniversalMA IndicatorFactory — wraps all 34 MA types from MovingAverageLibrary.

Usage
-----
>>> from src.indicators.ma_library import UniversalMA, MAType
>>> result = UniversalMA.run(close, window=14, ma_type="Jurik Moving Average")
>>> result.ma  # pd.Series / pd.DataFrame
"""

from collections import namedtuple

import numpy as np

from vectorbtpro.indicators.factory import IndicatorFactory

from src.indicators.nb.ma_library_nb import (
    MA_TYPE_NAMES,
    universal_ma_nb,
)

# ---------------------------------------------------------------------------
# MAType enum (NamedTuple for VBT param dtype mapping)
# ---------------------------------------------------------------------------
_fields = list(MA_TYPE_NAMES.keys())
_values = list(MA_TYPE_NAMES.values())
MAType = namedtuple("MAType", [f.replace(" ", "_").replace("'", "").replace("(", "").replace(")", "").replace("-", "_") for f in _fields])(*_values)

# Human-readable name → int lookup (for with_apply_func dtype mapping)
_ma_type_map = dict(MA_TYPE_NAMES)


def _resolve_ma_type(ma_type):
    """Convert string MA type name to integer code."""
    if isinstance(ma_type, (int, np.integer)):
        return int(ma_type)
    if isinstance(ma_type, str):
        if ma_type in _ma_type_map:
            return _ma_type_map[ma_type]
        raise ValueError(f"Unknown MA type: {ma_type!r}. Valid: {list(_ma_type_map.keys())}")
    return int(ma_type)


def _universal_ma_apply(close, window, ma_type, phase, power):
    """Apply function that resolves ma_type before calling Numba kernel."""
    mt = _resolve_ma_type(ma_type)
    return universal_ma_nb(close, int(window), int(mt), float(phase), float(power))


# ---------------------------------------------------------------------------
# IndicatorFactory registration
# ---------------------------------------------------------------------------
UniversalMA = IndicatorFactory(
    class_name="UniversalMA",
    module_name=__name__,
    input_names=["close"],
    param_names=["window", "ma_type"],
    output_names=["ma"],
    attr_settings=dict(
        close=dict(doc="Source price series."),
        ma=dict(doc="Moving average output series."),
    ),
).with_apply_func(
    _universal_ma_apply,
    kwargs_as_args=["phase", "power"],
    param_settings=dict(
        window=dict(doc="Lookback window size."),
        ma_type=dict(
            doc="Moving average type. Pass a string name or integer code.",
        ),
    ),
    window=14,
    ma_type="Jurik Moving Average",
    phase=0.0,
    power=2.0,
)
