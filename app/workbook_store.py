from dataclasses import dataclass
from threading import Lock
from uuid import UUID, uuid4

import pandas as pd

from app.models import WorkbookMetadata


@dataclass(frozen=True)
class Workbook:
    filename: str
    worksheet_name: str
    dataframe: pd.DataFrame


class WorkbookStore:
    """Process-local registry. A batch becomes visible only after validation."""

    def __init__(self) -> None:
        self._workbooks: dict[UUID, Workbook] = {}
        self._lock = Lock()

    def register_many(self, workbooks: list[Workbook]) -> list[WorkbookMetadata]:
        entries = {uuid4(): workbook for workbook in workbooks}
        with self._lock:
            self._workbooks.update(entries)
        return [
            WorkbookMetadata(
                workbook_id=key,
                filename=value.filename,
                worksheet_name=value.worksheet_name,
                columns=list(value.dataframe.columns),
            )
            for key, value in entries.items()
        ]

    def get(self, workbook_id: UUID) -> Workbook | None:
        with self._lock:
            return self._workbooks.get(workbook_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._workbooks)
