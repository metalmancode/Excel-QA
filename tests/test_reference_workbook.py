import pytest

from app.query_executor import execute_query
from app.query_validator import validate_plan
from app.schema_profiler import profile_schema
from conftest import make_plan


def test_reference_first_sheet_and_schema(reference_workbook):
    workbook = reference_workbook
    assert workbook.worksheet_name == "Sales_Data"
    assert workbook.dataframe.shape == (120, 14)
    assert list(workbook.dataframe.columns) == [
        "Order_ID", "Order_Date", "Country", "Region", "Product_Category", "Product",
        "Salesperson", "Quantity", "Unit_Price_EUR", "Discount_Pct", "Revenue_EUR",
        "Cost_EUR", "Profit_EUR", "Status",
    ]
    profile = profile_schema(workbook.dataframe)
    assert len(profile["columns"]) == 14
    assert profile["row_count"] == 120


@pytest.mark.parametrize("plan,expected", [
    (make_plan("count"), 120),
    (make_plan("count", column="Country", value="Germany"), 23),
    (make_plan("count", column="Country", value="France"), 21),
    (make_plan("count", column="Status", value="Completed"), 62),
    (make_plan("count", column="Status", value="Cancelled"), 29),
    (make_plan("count", column="Product_Category", value="Hardware"), 29),
    (make_plan("sum", "Revenue_EUR"), 651497.50),
    (make_plan("sum", "Revenue_EUR", "Country", "Germany"), 110207.50),
    (make_plan("sum", "Revenue_EUR", "Country", "France"), 98800.00),
    (make_plan("sum", "Profit_EUR"), 261038.06),
    (make_plan("sum", "Quantity"), 781),
])
def test_reference_golden_values(reference_workbook, plan, expected):
    frame = reference_workbook.dataframe
    assert execute_query(frame, validate_plan(frame, plan)) == pytest.approx(expected)
