from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Scalar = str | int | float | bool
Operation = Literal["filter", "sum", "count", "unsupported"]


class QueryPlan(BaseModel):
    """All fields are required for OpenAI strict structured outputs."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    operation: Operation
    target_column: str | None
    filter_column: str | None
    filter_value: Scalar | None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workbook_id: UUID
    question: str = Field(min_length=1, max_length=2000)


class WorkbookMetadata(BaseModel):
    workbook_id: UUID
    filename: str
    worksheet_name: str
    columns: list[str]


class UploadResponse(BaseModel):
    workbooks: list[WorkbookMetadata]


class ChatResponse(BaseModel):
    operation: Operation
    result: int | float | list[dict[str, Scalar | None]] | None
    filename: str
    worksheet_name: str
    message: str | None = None
