"""Opt-in paid evaluation. Plans and executor results are checked separately."""

import json
import os

import anyio
import pytest

from app.config import Settings
from app.llm_service import OpenAIPlanner
from app.query_executor import execute_query
from app.query_validator import validate_plan
from app.schema_profiler import profile_schema
from conftest import make_plan

CASES = [
    ("How many records are there?", make_plan("count"), 120),
    ("What is the total revenue?", make_plan("sum", "Revenue_EUR"), 651497.50),
    ("What is the total revenue for Germany?", make_plan("sum", "Revenue_EUR", "Country", "Germany"), 110207.50),
    ("What is the total profit?", make_plan("sum", "Profit_EUR"), 261038.06),
    ("How many records are there for France?", make_plan("count", column="Country", value="France"), 21),
    ("How many completed orders are there?", make_plan("count", column="Status", value="Completed"), 62),
    ("How many hardware orders are there?", make_plan("count", column="Product_Category", value="Hardware"), 29),
    ("Show all records for Germany.", make_plan("filter", column="Country", value="Germany"), 23),
    ("What is the average revenue?", make_plan("unsupported"), None),
    ("What is the total revenue for completed orders in Germany?", make_plan("unsupported"), None),
]


@pytest.fixture(scope="module")
def live_settings():
    if os.getenv("RUN_LIVE_LLM") != "1":
        pytest.skip("Real LLM evaluation is opt-in: set RUN_LIVE_LLM=1.")
    settings = Settings.from_env()
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY is not configured; live LLM evaluation was not executed.")
    return settings


@pytest.fixture(scope="module")
def live_report_path(live_settings):
    from pathlib import Path

    path = Path("reports/live-evaluation.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text("[]\n", encoding="utf-8")
    return path


@pytest.mark.live
@pytest.mark.parametrize("question,expected_plan,expected", CASES, ids=[case[0] for case in CASES])
def test_real_interpretation(live_settings, reference_workbook, live_report_path, question, expected_plan, expected, record_property):
    frame = reference_workbook.dataframe
    try:
        actual = anyio.run(OpenAIPlanner(live_settings).plan, question, profile_schema(frame))
    except Exception as exc:
        report = json.loads(live_report_path.read_text(encoding="utf-8"))
        report.append({"question": question, "provider_error_type": type(exc).__name__, "interpretation_correct": None, "execution_error": None})
        live_report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise
    interpretation_correct = actual == expected_plan
    result = None
    execution_error = None
    try:
        validated = validate_plan(frame, actual)
        if actual.operation != "unsupported":
            result = execute_query(frame, validated)
            if actual.operation == "filter":
                result = len(result)
    except ValueError as exc:
        execution_error = str(exc)
    record_property("interpretation_correct", interpretation_correct)
    record_property("execution_error", execution_error)
    record_property("actual_plan", actual.model_dump_json())
    record_property("calculated_result", json.dumps(result))
    report = json.loads(live_report_path.read_text(encoding="utf-8"))
    report.append({
        "question": question,
        "actual_plan": actual.model_dump(),
        "expected_plan": expected_plan.model_dump(),
        "interpretation_correct": interpretation_correct,
        "calculated_result": result,
        "expected_result": expected,
        "execution_error": execution_error,
        "result_correct": result == (pytest.approx(expected) if expected is not None else None),
    })
    live_report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert interpretation_correct, f"Interpretation error: expected {expected_plan}, received {actual}"
    assert execution_error is None, f"Execution error: {execution_error}"
    assert result == (pytest.approx(expected) if expected is not None else None)
