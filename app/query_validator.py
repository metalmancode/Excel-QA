from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype
from pydantic import ValidationError

from app.errors import InvalidPlan
from app.models import QueryPlan, Scalar


@dataclass(frozen=True)
class ValidatedPlan:
    operation: str
    target_column: str | None
    filter_column: str | None
    filter_value: Scalar | pd.Timestamp | None


def is_summable(series: pd.Series) -> bool:
    return is_numeric_dtype(series.dtype) and not is_bool_dtype(series.dtype)


def validate_plan(dataframe: pd.DataFrame, plan: QueryPlan) -> ValidatedPlan:
    try:
        # Revalidate even objects supplied by a custom planner/model_construct.
        plan = QueryPlan.model_validate(plan.model_dump())
    except (ValidationError, AttributeError) as exc:
        raise InvalidPlan("The planner returned an invalid query structure.") from exc

    has_column = plan.filter_column is not None
    has_value = plan.filter_value is not None
    if has_column != has_value:
        raise InvalidPlan("An exact-match filter needs both a column and a non-null value.")
    if plan.operation == "unsupported":
        if plan.target_column is not None or has_column or has_value:
            raise InvalidPlan("An unsupported plan must not contain executable fields.")
    elif plan.operation == "sum":
        if plan.target_column not in dataframe.columns:
            raise InvalidPlan("The sum target column does not exist.")
        if not is_summable(dataframe[plan.target_column]):
            raise InvalidPlan("Sum requires a numeric, non-boolean column.")
    elif plan.target_column is not None:
        raise InvalidPlan("Only sum accepts a target column.")
    if plan.operation == "filter" and not has_column:
        raise InvalidPlan("Filter requires one exact-match condition.")

    filter_value = plan.filter_value
    if has_column:
        if plan.filter_column not in dataframe.columns:
            raise InvalidPlan("The filter column does not exist.")
        column = dataframe[plan.filter_column]
        if is_datetime64_any_dtype(column.dtype):
            if not isinstance(filter_value, str):
                raise InvalidPlan("Date filters require an ISO 8601 string.")
            try:
                filter_value = pd.Timestamp(datetime.fromisoformat(filter_value))
                if pd.isna(filter_value) or filter_value.tzinfo is not None:
                    raise ValueError
            except (ValueError, OverflowError) as exc:
                raise InvalidPlan("Date filters require a valid timezone-free ISO 8601 value.") from exc
        elif is_bool_dtype(column.dtype):
            if not isinstance(filter_value, bool):
                raise InvalidPlan("Boolean filters require true or false.")
        elif is_numeric_dtype(column.dtype):
            if isinstance(filter_value, bool) or not isinstance(filter_value, (int, float)):
                raise InvalidPlan("Numeric filters require a numeric value.")
        elif not isinstance(filter_value, str):
            raise InvalidPlan("Text filters require a string value.")
    return ValidatedPlan(plan.operation, plan.target_column, plan.filter_column, filter_value)
