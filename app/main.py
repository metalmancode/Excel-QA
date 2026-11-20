from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.errors import InvalidPlan, InvalidWorkbook, PlannerUnavailable
from app.excel_service import load_excel
from app.llm_service import OpenAIPlanner, Planner
from app.models import ChatRequest, ChatResponse, UploadResponse
from app.query_executor import execute_query
from app.query_validator import validate_plan
from app.schema_profiler import profile_schema
from app.workbook_store import WorkbookStore


def create_app(settings: Settings | None = None, planner: Planner | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_env()
    api = FastAPI(title="Excel Q&A API", version="1.0.0")
    api.state.store = WorkbookStore()
    api.state.planner = planner if planner is not None else OpenAIPlanner(settings)

    @api.post("/upload", response_model=UploadResponse)
    async def upload(files: Annotated[list[UploadFile] | None, File()] = None) -> UploadResponse:
        """Validate a batch atomically, then register first-worksheet tables."""
        try:
            if not files or len(files) > settings.max_upload_files:
                raise InvalidWorkbook(f"Provide 1 to {settings.max_upload_files} files using the 'files' field.")
            workbooks = []
            for file in files:
                content = await file.read(settings.max_upload_bytes + 1)
                workbooks.append(await run_in_threadpool(load_excel, file.filename or "", content, settings))
            return UploadResponse(workbooks=api.state.store.register_many(workbooks))
        except InvalidWorkbook as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            for file in files or []:
                await file.close()

    @api.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        """Interpret once, validate against this workbook, calculate locally."""
        workbook = api.state.store.get(request.workbook_id)
        if workbook is None:
            raise HTTPException(status_code=404, detail="Workbook ID not found. Upload the workbook first.")
        try:
            schema = await run_in_threadpool(profile_schema, workbook.dataframe)
            plan = await api.state.planner.plan(request.question, schema)
            validated = await run_in_threadpool(validate_plan, workbook.dataframe, plan)
            if validated.operation == "unsupported":
                result = None
                message = "This question is unsupported or ambiguous. Ask for a row count, a numeric sum, or records with at most one exact-match filter."
            else:
                result = await run_in_threadpool(execute_query, workbook.dataframe, validated)
                message = None
        except InvalidPlan as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except PlannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return ChatResponse(
            operation=plan.operation,
            result=result,
            filename=workbook.filename,
            worksheet_name=workbook.worksheet_name,
            message=message,
        )

    return api


app = create_app()
