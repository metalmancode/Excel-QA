"""Convert Excel/pandas scalars to strict JSON values."""

from datetime import date, datetime
from decimal import Decimal
from math import isfinite
from numbers import Integral, Real

import pandas as pd

from app.models import Scalar


def json_scalar(value: object) -> Scalar | None:
    """Normalize workbook values for API responses and schema samples."""
    # Handle missing values before type conversion, including pandas NaT and NA.
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (bool, str)):
        return value
    # Convert numeric scalars to native JSON numbers and guard against infinity.
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, (Real, Decimal)):
        number = float(value)
        return number if isfinite(number) else None
    # NumPy bool is not a Python bool.
    if hasattr(value, "item"):
        return json_scalar(value.item())
    return str(value)
