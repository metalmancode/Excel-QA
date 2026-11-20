# Excel Q&A API

A small FastAPI service for uploading Excel workbooks and asking independent
natural-language questions. The LLM produces a constrained query plan. A
separate validator checks that plan against the selected DataFrame, and pandas
performs every filter, sum and count. There is no frontend or database.

## Installation

Python 3.11 or newer is required. Development was verified with Python 3.13.5.
Run these commands from the existing Deloitte project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
```

Set `OPENAI_API_KEY` in the local `.env` file or your shell environment. Do not
commit or share that file. A key is necessary for real `/chat` interpretation;
imports, uploads and the offline test suite work without one. The default model
is `gpt-4.1-mini`, configurable through `OPENAI_MODEL`. Your API project must
have access to the selected model and billing enabled.

The integration uses `AsyncOpenAI.responses.parse(text_format=QueryPlan)` with
a Pydantic schema, rather than a plain-text request to return JSON. See the
[official structured output guide](https://developers.openai.com/api/docs/guides/structured-outputs)
and the [model's supported features](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
Structured output validates shape; semantic validation remains a separate step.

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Open [Swagger UI](http://127.0.0.1:8000/docs). Both endpoints are available
through **Try it out**. For `/upload`, add one or more files under the `files`
field. Copy a returned workbook ID into a `/chat` request.

Use one worker. Data is held in that process only and is lost on restart,
including a development reload. Workers do not share workbook IDs.

## API examples

Upload one or multiple files using the repeated multipart field `files`:

```bash
curl --fail-with-body http://127.0.0.1:8000/upload \
  -F 'files=@/absolute/path/to/sales.xlsx' \
  -F 'files=@/absolute/path/to/inventory.xlsx'
```

Each result contains `workbook_id`, `filename`, `worksheet_name` and every
available `columns` entry. Only the first worksheet of each file is read.
All files are validated before any workbook in that batch is registered.

Replace the example UUID below with one returned by `/upload`:

```bash
curl --fail-with-body http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"workbook_id":"00000000-0000-4000-8000-000000000000","question":"What is the total revenue for Germany?"}'
```

With the supplied employer workbook uploaded as `sales.xlsx`, the response is:

```json
{
  "operation": "sum",
  "result": 110207.5,
  "filename": "sales.xlsx",
  "worksheet_name": "Sales_Data",
  "message": null
}
```

Application logic contains no dataset-specific names or value mappings.

| Operation | Behavior |
| --- | --- |
| `filter` | Entire records matching one exact value in one column |
| `sum` | Total of one numeric column, optionally with one equality filter |
| `count` | Number of rows, optionally with one equality filter |
| `unsupported` | HTTP 200, `result: null`, and a clear scope/ambiguity message |

For example, counts and sums can target other compatible tables with entirely
different column names. Averages, grouping, distinct counts, ranges, ordering,
derived calculations and two simultaneous filters are unsupported.

| Status | Meaning |
| --- | --- |
| 200 | Successful upload/query, including a handled unsupported question |
| 400 | Invalid workbook, absent files, excessive file count or upload limit |
| 404 | Unknown workbook ID |
| 422 | Invalid request, invalid model plan, missing columns or nonnumeric sum |
| 503 | Missing API key, provider error/timeout, refusal or unparseable response |

Malformed UUIDs fail request validation with 422. Unknown well-formed UUIDs
return 404 without calling the LLM. Provider error details are never exposed.

## Architecture

```text
/upload -> Excel loader -> per-process workbook store
/chat   -> workbook lookup -> bounded schema profile -> OpenAI planner
        -> semantic validation -> deterministic pandas executor -> JSON
```

- `excel_service.py` opens XLSX with openpyxl, validates raw headers before
  creating a pandas DataFrame, and reads only worksheet zero.
- `workbook_store.py` assigns UUID4 IDs and registers batches under a lock.
  Each application instance owns its own store.
- `schema_profiler.py` supplies types, null/unique counts and bounded values.
  It sends up to 20 distinct values for categorical columns and 5 samples for
  columns with more than 20 distinct values. Sample strings are capped at 160
  characters. The profile indicates whether samples are exhaustive.
- `llm_service.py` makes one asynchronous model request per valid chat request.
  The prompt constrains interpretation and treats worksheet content as
  untrusted data. It sends no full table and enables no tools. `store=False`
  disables application response storage at the provider; the question, headers
  and sampled values are still transmitted to OpenAI.
- `query_validator.py` rejects invalid field combinations, missing columns,
  incompatible filter types and sums of text, dates or booleans. It revalidates
  model objects independently of SDK parsing.
- `query_executor.py` accepts validated plans and performs only pandas equality
  selection, row counting and summation. It neither calls the model nor runs
  model-generated code or expressions.
- `main.py` composes the service and maps errors to HTTP responses. Excel
  parsing, profiling and query execution run in worker threads; the model call
  uses the async SDK with a timeout and no automatic retries.

FastAPI supplies typed request validation and interactive OpenAPI docs. pandas
provides simple, independently testable table operations. The constrained plan
keeps calculations reproducible and makes model errors inspectable. A
process-local store satisfies the assignment without deployment infrastructure.
LangChain, RAG, databases and task queues add no value to these three operations.

## Data semantics and limits

- Headers must be nonempty text. Surrounding header whitespace is trimmed;
  duplicates after trimming are rejected. Matching uses those resulting names.
- A worksheet needs at least one data row. Completely empty rows are ignored;
  partially empty rows are preserved. Additional nonempty columns without a
  header are rejected. The workbook must be readable. Only data in the first
  worksheet can be queried.
- String equality is case-sensitive and exact, with no substring search,
  fuzzy matching or trimming of cell values. For an unambiguous category the
  planner can resolve the user's wording to its exact spelling in the schema.
- Numeric filters need JSON numbers. Boolean filters use JSON `true` or
  `false`. Blank cells in a boolean column remain missing and match neither
  value. Numeric-looking text remains text. Sums skip missing values, including
  when the entire numeric column is missing. No matches yield `[]` for
  filter and `0` for count/sum. Count uses row count, never non-null cell count.
- Null equality filtering is outside scope. Date filters use timezone-free ISO
  8601 equality. A date without a time means midnight, not a whole-day range.
- Floating values are converted to decimal representations before pandas
  summation to reduce binary addition artifacts, then returned as JSON numbers.
  Integer sums use Python integers to avoid fixed-width overflow. Excel input
  and JSON numbers still have finite precision; this is not an accounting
  decimal API. Queries do not mutate stored DataFrames.
- Dates/timestamps become ISO 8601 strings. Missing values become JSON null.
  Non-finite cells become null in records and are rejected as sum inputs;
  NaN/Infinity are never emitted as JSON numbers.
- Formula cells use their cached Excel values. The service does not calculate
  formulas. A workbook saved without cached results may therefore contain nulls.
- Defaults: 5 MiB per file, 10 files per request, 50 MiB total uncompressed ZIP
  members per workbook, 100,000 worksheet rows and 256 columns. Limits are
  configurable using the corresponding variables in `.env.example`. The file
  limit is checked while reading the uploaded file, after multipart parsing;
  it is not a production HTTP-body gate or a cumulative memory quota.
- LLM timeout defaults to 30 seconds (`LLM_TIMEOUT_SECONDS`). No key is needed
  until a query reaches interpretation.

## Testing

```bash
source .venv/bin/activate
python -m pytest -v
```

Unit tests exercise generic DataFrames without any network calls. API tests use
TestClient with an injected planner. SDK adapter tests mock the provider and
check structured-output settings and sanitized failures. Live tests are skipped
by default and require an API key when enabled.

The employer workbook is confidential and excluded from Git. Point the tests
at a local copy without copying it into the repository:

```bash
EXCEL_REFERENCE_PATH='/absolute/path/to/excel_chatbot_sample 1.xlsx' \
  python -m pytest -v
```

Alternatively place it in `tests/fixtures/`. Without a reference file, the 12
reference tests skip with an explicit reason. They verify the first worksheet,
120 rows, 14 columns and all 11 supplied golden calculations.

To run the ten evaluation questions against the configured model, set the API
key locally and opt in. These requests incur normal provider usage.

```bash
mkdir -p reports
RUN_LIVE_LLM=1 EXCEL_REFERENCE_PATH='/absolute/path/to/excel_chatbot_sample 1.xlsx' \
  python -m pytest -v -m live --junitxml=reports/live-evaluation.xml
```

The local JSON report (`reports/live-evaluation.json`) records the actual plan,
whether interpretation matched the expected plan, the calculated result, and
any execution error. The optional JUnit report also includes test properties.
Provider failure fails the test. Missing credentials or a missing workbook
cause explicit skips. The report may contain employer schema information and
is kept local.

### Verification results on 20 November 2026

| Check | Result |
| --- | --- |
| Offline suite with the employer workbook | 122 passed, including all 12 reference checks and both boolean filter cases with a blank cell. |
| Previous live OpenAI evaluation with the employer workbook | 10 of 10 passed with `gpt-4.1-mini`, including the two-condition request that must return `unsupported`. |
| Interactive API check with the employer workbook | 10 of 10 questions matched the expected responses. |
| Interactive API check with a synthetic maintenance workbook | 17 of 17 questions matched the expected responses. |

For the interactive checks, an assistant received each question and the sheet
schema, then returned a JSON query plan. FastAPI's TestClient exercised
`/upload` and `/chat`, including validation and pandas execution. The check on
the synthetic workbook used different column names and data types. For example,
summing `Hours_Worked` for `Workshop = Central` returned `5.5`. The checks also
covered the first sheet rule, blank values, date and boolean filters, zero
matches and unsupported requests.

Uvicorn startup, `/docs` and a reference upload were also verified locally.
The live evaluation checked both the model's query plans and the calculated
results against the expected outcomes for those ten questions.

## Known limitations and possible improvements

This is a single-process interview assignment service. It has no authentication,
durable storage, conversation memory, pagination, total registry memory limit,
retention cleanup or production-grade scalability. Filter responses return all
matching records. Do not expose it publicly as a production service.

Strict output and semantic checks do not prove that a valid plan faithfully
represents every natural-language request. The planner prompt addresses
ambiguity, and the live evaluation covers a fixed set of ten questions. Prompt
instructions alone do not eliminate prompt injection. The security boundary is
the finite operation schema, validation, absence of execution tools and fixed
executor. Headers and sampled cells are disclosed to the configured provider.

Future changes could add authentication, retention limits, shared storage and
bounded result pagination when justified. Average or Group By would require
explicit plan-schema additions, matching validation/executor changes and new
tests, rather than more permissive model-generated expressions.
