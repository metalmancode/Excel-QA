# Local reference workbook

The employer's confidential XLSX is intentionally excluded from Git. Either
place it here as `excel_chatbot_sample 1.xlsx`, or set `EXCEL_REFERENCE_PATH`
to its existing absolute path. Reference tests skip explicitly when unavailable.
Synthetic workbooks are generated in memory by `tests/conftest.py`.
