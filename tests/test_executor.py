import json

import numpy as np
import pandas as pd
import pytest

from app.errors import InvalidPlan
from app.query_executor import execute_query
from app.query_validator import validate_plan
from app.serialization import json_scalar
from conftest import make_plan


@pytest.mark.parametrize("plan,expected", [
    (make_plan("sum", "Units"), 10),
    (make_plan("sum", "Units", "Depot", "North"), 2.5),
    (make_plan("count"), 4),
    (make_plan("count", column="Depot", value="North"), 2),
    (make_plan("count", column="Depot", value="West"), 0),
    (make_plan("sum", "Units", "Depot", "West"), 0),
    (make_plan("count", column="Depot", value="north"), 0),
    (make_plan("count", column="Depot", value="Nor"), 0),
    (make_plan("count", column="Active", value=True), 2),
    (make_plan("count", column="Units", value=7), 1),
    (make_plan("count", column="Recorded", value="2026-01-01"), 1),
])
def test_calculations(frame, plan, expected):
    original = frame.copy(deep=True)
    assert execute_query(frame, validate_plan(frame, plan)) == pytest.approx(expected)
    pd.testing.assert_frame_equal(original, frame)


def test_filter_and_strict_json(frame):
    plan = make_plan("filter", column="Depot", value="North")
    result = execute_query(frame, validate_plan(frame, plan))
    assert len(result) == 2
    assert result[0]["Recorded"] == "2026-01-01T00:00:00"
    assert result[1]["Units"] is None
    assert result[1]["Recorded"] is None
    json.dumps(result, allow_nan=False)


def test_no_filter_matches(frame):
    plan = make_plan("filter", column="Depot", value="Nowhere")
    assert execute_query(frame, validate_plan(frame, plan)) == []


def test_unsupported_cannot_execute(frame):
    with pytest.raises(InvalidPlan, match="Only validated"):
        execute_query(frame, validate_plan(frame, make_plan("unsupported")))


def test_unvalidated_plan_cannot_execute(frame):
    with pytest.raises(InvalidPlan):
        execute_query(frame, make_plan())


@pytest.mark.parametrize("value,expected", [
    (np.int64(7), 7), (np.float64(2.5), 2.5), (np.bool_(True), True),
    (float("nan"), None), (float("inf"), None), (-float("inf"), None),
    (pd.NaT, None), (pd.NA, None),
])
def test_scalar_serialization(value, expected):
    assert json_scalar(value) == expected


def test_large_integer_sum_does_not_overflow():
    frame = pd.DataFrame({"Value": [2**62, 2**62]})
    assert execute_query(frame, validate_plan(frame, make_plan("sum", "Value"))) == 2**63


def test_float_sum_avoids_binary_addition_artifacts():
    frame = pd.DataFrame({"Value": [0.1, 0.2]})
    assert execute_query(frame, validate_plan(frame, make_plan("sum", "Value"))) == 0.3


def test_all_null_numeric_sum_is_zero():
    frame = pd.DataFrame({"Value": pd.Series([None, None], dtype="float64")})
    assert execute_query(frame, validate_plan(frame, make_plan("sum", "Value"))) == 0


def test_nonfinite_sum_rejected():
    frame = pd.DataFrame({"Value": [float("inf")]})
    with pytest.raises(InvalidPlan, match="non-finite"):
        execute_query(frame, validate_plan(frame, make_plan("sum", "Value")))
