"""Describe the selected table to the planner using bounded samples."""

import pandas as pd

from app.query_validator import is_summable
from app.serialization import json_scalar


def profile_schema(dataframe: pd.DataFrame) -> dict:
    """Report observed column types, missing values and sample filter values."""
    columns = []
    for name in dataframe.columns:
        series = dataframe[name]
        # Show small category sets in full and limit samples from larger sets.
        unique = series.dropna().unique()
        limit = 20 if len(unique) <= 20 else 5
        samples = [json_scalar(value) for value in unique[:limit]]
        truncated = any(isinstance(value, str) and len(value) > 160 for value in samples)
        # Tell the planner when value count or text length forced truncation.
        columns.append({
            "name": name,
            "dtype": str(series.dtype),
            "numeric": is_summable(series),
            "null_count": int(series.isna().sum()),
            "unique_count": len(unique),
            "sample_values": [value[:160] if isinstance(value, str) else value for value in samples],
            "samples_exhaustive": len(unique) <= limit and not truncated,
        })
    return {"row_count": len(dataframe), "columns": columns}
