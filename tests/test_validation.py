import pytest
from pydantic import ValidationError

from app.errors import InvalidPlan
from app.models import QueryPlan
from app.query_validator import validate_plan
from conftest import make_plan


@pytest.mark.parametrize("plan", [
    make_plan("sum", "Depot"),
    make_plan("sum", "Active"),
    make_plan("sum", "Missing"),
    make_plan("sum"),
    make_plan("count", column="Missing", value="North"),
    make_plan("count", column="Depot"),
    make_plan("count", value="North"),
    make_plan("filter"),
    make_plan("count", target="Units"),
    make_plan("filter", target="Units", column="Depot", value="North"),
    make_plan("unsupported", "Units"),
    make_plan("unsupported", column="Depot", value="North"),
    make_plan("count", column="Units", value="7"),
    make_plan("count", column="Units", value=True),
    make_plan("count", column="Active", value=1),
    make_plan("count", column="Depot", value=1),
    make_plan("count", column="Recorded", value="yesterday"),
    make_plan("count", column="Recorded", value="2026-01-01T00:00:00+00:00"),
])
def test_invalid_semantics(frame, plan):
    with pytest.raises(InvalidPlan):
        validate_plan(frame, plan)


@pytest.mark.parametrize("overrides", [
    {"operation": "average"}, {"filter_value": ["North", "South"]},
    {"filters": []}, {"filter_value": float("nan")}, {"filter_value": float("inf")},
])
def test_invalid_structure(overrides):
    payload = make_plan().model_dump() | overrides
    with pytest.raises(ValidationError):
        QueryPlan.model_validate(payload)


def test_model_construct_cannot_bypass_validation(frame):
    plan = QueryPlan.model_construct(operation="delete", target_column=None, filter_column=None, filter_value=None)
    with pytest.raises(InvalidPlan):
        validate_plan(frame, plan)
