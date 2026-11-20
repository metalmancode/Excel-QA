"""Parse only the first worksheet and validate headers before pandas sees them."""

from io import BytesIO
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile

import pandas as pd
from openpyxl import load_workbook

from app.config import Settings
from app.errors import InvalidWorkbook
from app.workbook_store import Workbook


def load_excel(filename: str, content: bytes, settings: Settings) -> Workbook:
    if PurePath(filename).suffix.lower() != ".xlsx":
        raise InvalidWorkbook("Only .xlsx files are accepted.")
    if not content or len(content) > settings.max_upload_bytes:
        raise InvalidWorkbook("File is empty or exceeds MAX_UPLOAD_BYTES.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > settings.max_xlsx_uncompressed_bytes:
                raise InvalidWorkbook("Workbook exceeds the expanded XLSX size limit.")
    except BadZipFile as exc:
        raise InvalidWorkbook("File is not a readable XLSX workbook.") from exc

    try:
        # data_only uses cached formula values. Never evaluate workbook formulas.
        book = load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            sheet = book.worksheets[0]
            sheet_name = sheet.title
            # Do not trust a producer's dimension metadata when reading rows.
            sheet.reset_dimensions()
            rows = sheet.iter_rows(values_only=True)
            raw_headers = next(rows, ())
            if not raw_headers or len(raw_headers) > settings.max_worksheet_columns:
                raise InvalidWorkbook("The first worksheet has no headers or too many columns.")
            if any(not isinstance(value, str) or not value.strip() for value in raw_headers):
                raise InvalidWorkbook("Each column must have a nonempty text header.")
            headers = [value.strip() for value in raw_headers]
            if len(set(headers)) != len(headers):
                raise InvalidWorkbook("Duplicate column headers are not allowed.")
            data = []
            for index, row in enumerate(rows, start=1):
                if index > settings.max_worksheet_rows:
                    raise InvalidWorkbook("Worksheet exceeds the row limit.")
                if len(row) > len(headers) and any(value is not None for value in row[len(headers):]):
                    raise InvalidWorkbook("Data appears in a column without a header.")
                if any(value is not None for value in row):
                    data.append(tuple(row[:len(headers)]) + (None,) * max(0, len(headers) - len(row)))
            if not data:
                raise InvalidWorkbook("The first worksheet must contain at least one data row.")
        finally:
            book.close()
    except InvalidWorkbook:
        raise
    except Exception as exc:
        # Parser failures contain untrusted XML, paths and implementation details.
        raise InvalidWorkbook("File is not a readable XLSX workbook.") from exc
    return Workbook(filename, sheet_name, pd.DataFrame(data, columns=headers))
