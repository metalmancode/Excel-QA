import json

import pandas as pd

from app.schema_profiler import profile_schema


def test_profile_generic_schema(frame):
    result = profile_schema(frame)
    columns = {item["name"]: item for item in result["columns"]}
    assert result["row_count"] == 4
    assert columns["Depot"]["unique_count"] == 2
    assert columns["Depot"]["sample_values"] == ["North", "South"]
    assert columns["Units"]["numeric"] is True
    assert columns["Active"]["numeric"] is False
    assert columns["Recorded"]["null_count"] == 1
    json.dumps(result, allow_nan=False)


def test_bounded_and_truncated_samples():
    frame = pd.DataFrame({"Identifier": [f"Unique-{i}" for i in range(100)], "Notes": ["x" * 1000] * 100})
    profile = profile_schema(frame)["columns"]
    assert len(profile[0]["sample_values"]) == 5
    assert profile[0]["unique_count"] == 100
    assert profile[0]["samples_exhaustive"] is False
    assert len(profile[1]["sample_values"][0]) == 160
    assert profile[1]["samples_exhaustive"] is False
