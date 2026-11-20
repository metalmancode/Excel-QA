from datetime import datetime
from io import BytesIO
import os
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from app.models import QueryPlan
from app.config import Settings
from app.excel_service import load_excel


def make_xlsx(headers=None, rows=None, second_sheet=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inventory"
    if headers is not None:
        sheet.append(headers)
    for row in rows or []:
        sheet.append(row)
    if second_sheet:
        workbook.create_sheet("Ignored").append(["Wrong column"])
        workbook.worksheets[1].append([9999])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def make_plan(operation="count", target=None, column=None, value=None):
    return QueryPlan(operation=operation, target_column=target, filter_column=column, filter_value=value)


@pytest.fixture
def frame():
    return pd.DataFrame({
        "Depot": ["North", "South", "North", None],
        "Units": [2.5, 7.0, None, 0.5],
        "Active": [True, False, True, False],
        "Recorded": [datetime(2026, 1, 1), datetime(2026, 1, 2), None, datetime(2026, 1, 4)],
    })


@pytest.fixture
def xlsx():
    return make_xlsx(["Depot", "Units"], [["North", 2.5], ["South", 7], ["North", 3]], True)


@pytest.fixture(scope="session")
def reference_workbook():
    path = Path(os.getenv("EXCEL_REFERENCE_PATH", "tests/fixtures/excel_chatbot_sample 1.xlsx"))
    if not path.is_file():
        pytest.skip("Employer workbook unavailable; set EXCEL_REFERENCE_PATH to its local path.")
    return load_excel(path.name, path.read_bytes(), Settings())
