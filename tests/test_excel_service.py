import pytest

from app.config import Settings
from app.errors import InvalidWorkbook
from app.excel_service import load_excel
from conftest import make_xlsx


def test_first_worksheet(xlsx):
    result = load_excel("book.xlsx", xlsx, Settings())
    assert result.filename == "book.xlsx"
    assert result.worksheet_name == "Inventory"
    assert result.dataframe.shape == (3, 2)


@pytest.mark.parametrize("headers,rows", [
    (None, None), (["A"], []), ([None, "B"], [[1, 2]]),
    (["  ", "B"], [[1, 2]]), (["A", "A"], [[1, 2]]),
    (["A", " A "], [[1, 2]]), ([1, "B"], [[1, 2]]),
    (["A"], [[1, 2]]),
])
def test_invalid_headers_or_empty_sheet(headers, rows):
    with pytest.raises(InvalidWorkbook):
        load_excel("book.xlsx", make_xlsx(headers, rows), Settings())


def test_size_and_expansion_limits(xlsx):
    with pytest.raises(InvalidWorkbook):
        load_excel("book.xlsx", xlsx, Settings(max_upload_bytes=10))
    with pytest.raises(InvalidWorkbook, match="expanded"):
        load_excel("book.xlsx", xlsx, Settings(max_xlsx_uncompressed_bytes=10))


def test_row_and_column_limits(xlsx):
    with pytest.raises(InvalidWorkbook, match="row limit"):
        load_excel("book.xlsx", xlsx, Settings(max_worksheet_rows=1))
    with pytest.raises(InvalidWorkbook, match="too many columns"):
        load_excel("book.xlsx", xlsx, Settings(max_worksheet_columns=1))


def test_blank_rows_and_uncached_formulas():
    content = make_xlsx(["Label", "Amount"], [["Kept", "=1+1"], [None, None], ["Partial", 3]])
    result = load_excel("book.xlsx", content, Settings()).dataframe
    assert len(result) == 2
    assert result["Amount"].isna().sum() == 1


def test_invalid_second_sheet_is_ignored():
    content = make_xlsx(["Amount"], [[3]], second_sheet=True)
    assert load_excel("book.xlsx", content, Settings()).dataframe["Amount"].sum() == 3
