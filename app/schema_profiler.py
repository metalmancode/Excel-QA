import pandas as pd

from app.query_validator import is_summable
from app.serialization import json_scalar


def profile_schema(dataframe: pd.DataFrame) -> dict:
    columns = []
    for name in dataframe.columns:
        series = dataframe[name]
        unique = series.dropna().unique()
        limit = 20 if len(unique) <= 20 else 5
        samples = [json_scalar(value) for value in unique[:limit]]
        truncated = any(isinstance(value, str) and len(value) > 160 for value in samples)
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
