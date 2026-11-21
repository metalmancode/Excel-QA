from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from conftest import make_xlsx


@pytest.fixture
def client():
    with TestClient(create_app(Settings())) as value:
        yield value


def test_upload_metadata(client, xlsx):
    response = client.post("/upload", files=[("files", ("example.xlsx", xlsx))])
    assert response.status_code == 200
    metadata = response.json()["workbooks"][0]
    assert UUID(metadata["workbook_id"]).version == 4
    assert metadata["filename"] == "example.xlsx"
    assert metadata["worksheet_name"] == "Inventory"
    assert metadata["columns"] == ["Depot", "Units"]


def test_multiple_uploads_are_independent(client, xlsx):
    response = client.post("/upload", files=[("files", (name, xlsx)) for name in ["one.xlsx", "two.xlsx"]])
    assert response.status_code == 200
    first, second = response.json()["workbooks"]
    assert first["workbook_id"] != second["workbook_id"]
    store = client.app.state.store
    assert len(store) == 2
    assert store.get(UUID(first["workbook_id"])).dataframe is not store.get(UUID(second["workbook_id"])).dataframe


@pytest.mark.parametrize("filename,content", [("book.csv", b"a,b"), ("book.xlsx", b"broken"), ("book.xlsx", b"")])
def test_invalid_file(client, filename, content):
    assert client.post("/upload", files=[("files", (filename, content))]).status_code == 400
    assert len(client.app.state.store) == 0


def test_atomic_batch_rejection(client, xlsx):
    response = client.post("/upload", files=[("files", ("ok.xlsx", xlsx)), ("files", ("bad.xlsx", b"bad"))])
    assert response.status_code == 400
    assert len(client.app.state.store) == 0


def test_upload_size_limit(xlsx):
    with TestClient(create_app(Settings(max_upload_bytes=100))) as client:
        assert client.post("/upload", files=[("files", ("book.xlsx", xlsx))]).status_code == 400


def test_upload_file_count_limit(xlsx):
    with TestClient(create_app(Settings(max_upload_files=1))) as client:
        assert client.post("/upload", files=[("files", ("book.xlsx", xlsx))] * 2).status_code == 400


@pytest.mark.parametrize("headers,rows", [(["A", "A"], [[1, 2]]), ([None, "B"], [[1, 2]]), (None, None)])
def test_bad_worksheet(client, headers, rows):
    content = make_xlsx(headers, rows)
    assert client.post("/upload", files=[("files", ("book.xlsx", content))]).status_code == 400


def test_missing_files(client):
    assert client.post("/upload").status_code == 400


def test_docs_and_openapi(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert {"/upload", "/chat"} <= schema["paths"].keys()
    multipart = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["multipart/form-data"]
    body_name = multipart["schema"]["$ref"].rsplit("/", 1)[-1]
    files = schema["components"]["schemas"][body_name]["properties"]["files"]
    assert files["type"] == "array"
    assert files["items"]["format"] == "binary"
