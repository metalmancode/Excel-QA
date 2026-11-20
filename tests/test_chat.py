from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import PlannerUnavailable
from app.main import create_app
from conftest import make_plan, make_xlsx


@pytest.fixture
def chat_context(xlsx):
    planner = AsyncMock()
    planner.plan.return_value = make_plan("sum", "Units", "Depot", "North")
    with TestClient(create_app(Settings(), planner)) as client:
        workbook_id = client.post("/upload", files=[("files", ("book.xlsx", xlsx))]).json()["workbooks"][0]["workbook_id"]
        yield client, planner, workbook_id


def test_chat_calculates_and_sends_only_schema(chat_context):
    client, planner, workbook_id = chat_context
    response = client.post("/chat", json={"workbook_id": workbook_id, "question": "Total units in North?"})
    assert response.status_code == 200
    assert response.json() == {"operation": "sum", "result": 5.5, "filename": "book.xlsx", "worksheet_name": "Inventory", "message": None}
    question, schema = planner.plan.call_args.args
    assert question == "Total units in North?"
    assert "columns" in schema and "records" not in schema
    planner.plan.assert_awaited_once()


@pytest.mark.parametrize("plan,expected", [
    (make_plan("count"), 3),
    (make_plan("count", column="Depot", value="Unknown"), 0),
    (make_plan("filter", column="Depot", value="North"), [{"Depot": "North", "Units": 2.5}, {"Depot": "North", "Units": 3}]),
    (make_plan("filter", column="Depot", value="Unknown"), []),
])
def test_other_results(chat_context, plan, expected):
    client, planner, workbook_id = chat_context
    planner.plan.return_value = plan
    response = client.post("/chat", json={"workbook_id": workbook_id, "question": "A valid question"})
    assert response.status_code == 200
    assert response.json()["result"] == expected


@pytest.mark.parametrize(
    ("active", "expected_device"),
    [(True, "Printer"), (False, "Scanner")],
)
def test_filter_boolean_column_with_a_blank_cell(active, expected_device):
    """Excel blanks should match neither true nor false."""
    workbook = make_xlsx(
        ["Device", "Active"],
        [["Printer", True], ["Monitor", None], ["Scanner", False]],
    )
    planner = AsyncMock()
    planner.plan.return_value = make_plan("filter", column="Active", value=active)

    with TestClient(create_app(Settings(), planner)) as client:
        upload = client.post("/upload", files=[("files", ("devices.xlsx", workbook))])
        assert upload.status_code == 200
        workbook_id = upload.json()["workbooks"][0]["workbook_id"]
        response = client.post(
            "/chat",
            json={
                "workbook_id": workbook_id,
                "question": f"Show devices with Active = {str(active).lower()}",
            },
        )

    assert response.status_code == 200, response.json()
    records = response.json()["result"]
    assert records == [{"Device": expected_device, "Active": active}]
    assert records[0]["Active"] is active


def test_unknown_workbook_does_not_call_model(chat_context):
    client, planner, _ = chat_context
    assert client.post("/chat", json={"workbook_id": str(uuid4()), "question": "Count rows"}).status_code == 404
    planner.plan.assert_not_called()


@pytest.mark.parametrize("question", ["", "   ", None, "a" * 2001, 123])
def test_invalid_question(chat_context, question):
    client, planner, workbook_id = chat_context
    assert client.post("/chat", json={"workbook_id": workbook_id, "question": question}).status_code == 422
    planner.plan.assert_not_called()


def test_unsupported(chat_context):
    client, planner, workbook_id = chat_context
    planner.plan.return_value = make_plan("unsupported")
    response = client.post("/chat", json={"workbook_id": workbook_id, "question": "Average units by depot?"})
    assert response.status_code == 200
    assert response.json()["result"] is None
    assert "unsupported" in response.json()["message"]


@pytest.mark.parametrize("plan", [make_plan("sum", "Depot"), make_plan("sum", "MadeUp"), make_plan("count", column="MadeUp", value="North")])
def test_invalid_plan_never_reaches_executor(chat_context, monkeypatch, plan):
    client, planner, workbook_id = chat_context
    planner.plan.return_value = plan
    def fail_if_called(*args):
        pytest.fail("An invalid plan reached the executor")
    monkeypatch.setattr("app.main.execute_query", fail_if_called)
    assert client.post("/chat", json={"workbook_id": workbook_id, "question": "Total?"}).status_code == 422


def test_provider_failure(chat_context):
    client, planner, workbook_id = chat_context
    planner.plan.side_effect = PlannerUnavailable("LLM interpretation is unavailable.")
    assert client.post("/chat", json={"workbook_id": workbook_id, "question": "Count"}).status_code == 503


def test_missing_key_is_safe(xlsx):
    with TestClient(create_app(Settings())) as client:
        workbook_id = client.post("/upload", files=[("files", ("book.xlsx", xlsx))]).json()["workbooks"][0]["workbook_id"]
        response = client.post("/chat", json={"workbook_id": workbook_id, "question": "Count"})
        assert response.status_code == 503
        assert "OPENAI_API_KEY" in response.json()["detail"]


def test_workbook_isolation(chat_context):
    client, planner, first_id = chat_context
    other = make_xlsx(["Depot", "Units"], [["North", 100]])
    second_id = client.post("/upload", files=[("files", ("other.xlsx", other))]).json()["workbooks"][0]["workbook_id"]
    for key, expected in [(first_id, 5.5), (second_id, 100), (first_id, 5.5)]:
        assert client.post("/chat", json={"workbook_id": key, "question": "Total units in North?"}).json()["result"] == expected
