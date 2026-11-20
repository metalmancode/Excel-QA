"""Environment configuration; importing the application needs no API key."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Keep model settings and workbook size limits together."""

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = 30
    max_upload_bytes: int = 5 * 1024 * 1024
    max_upload_files: int = 10
    max_xlsx_uncompressed_bytes: int = 50 * 1024 * 1024
    max_worksheet_rows: int = 100_000
    max_worksheet_columns: int = 256

    def __post_init__(self) -> None:
        # Reject unusable limits at startup rather than on the first request.
        for field in self.__dataclass_fields__:
            if field.startswith("max_") or field == "llm_timeout_seconds":
                if getattr(self, field) <= 0:
                    raise ValueError(f"{field} must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        """Read environment configuration and fill in missing values from defaults."""

        load_dotenv()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "").strip() or "gpt-4.1-mini",
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            # Use each max_* field's default unless its uppercase env var is set.
            **{
                name: int(os.getenv(name.upper(), str(field.default)))
                for name, field in cls.__dataclass_fields__.items()
                if name.startswith("max_")
            },
        )
