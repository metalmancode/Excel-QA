"""Deterministic pandas operations; no model calls or generated expressions."""

from decimal import Decimal

import pandas as pd
from pandas.api.types import is_float_dtype

from app.errors import InvalidPlan
from app.query_validator import ValidatedPlan
from app.serialization import json_scalar


def execute_query(dataframe: pd.DataFrame, plan: ValidatedPlan) -> int | float | list[dict]:
    """Run one supported operation against an already validated workbook plan."""
    if not isinstance(plan, ValidatedPlan) or plan.operation not in {"filter", "sum", "count"}:
        raise InvalidPlan("Only validated filter, sum and count plans can be executed.")
    # Use the same exact-match selection for all three operations.
    selected = dataframe
    if plan.filter_column is not None:
        selected = dataframe.loc[dataframe[plan.filter_column].eq(plan.filter_value).fillna(False)]
    # Count selected rows even when some of their cells are blank.
    if plan.operation == "count":
        return len(selected)
    # Convert each matching row to a JSON-compatible record with its column labels.
    if plan.operation == "filter":
        return [
            {column: json_scalar(value) for column, value in zip(selected.columns, row)}
            for row in selected.itertuples(index=False, name=None)
        ]
    # A SUM operates on the validated numeric column and ignores blank cells.
    column = selected[plan.target_column].dropna()
    if is_float_dtype(column.dtype):
        # Decimal(str(...)) removes binary addition artifacts without rounding
        # every workbook to a currency-specific number of decimal places.
        if any(json_scalar(value) is None for value in column):
            raise InvalidPlan("Cannot sum non-finite numeric values.")
        total = column.map(lambda value: Decimal(str(value))).sum()
    else:
        # Python integers avoid fixed-width NumPy overflow during pandas sum.
        total = column.astype(object).sum()
    result = json_scalar(total)
    if result is None:
        raise InvalidPlan("The sum cannot be represented as a finite JSON number.")
    return result
