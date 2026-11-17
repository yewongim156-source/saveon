# Save:On Developer API

Internal observability API for Save:On agent and tool executions.

## Responsibilities

- ingest idempotent trace events from the AI pipeline;
- materialize trace sessions and pipeline steps;
- keep the raw event stream for timeline replay;
- expose overview, session-list, and session-detail APIs;
- stay outside the user request path so telemetry failures do not fail analysis.

## Run

```powershell
cd developer-api
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn main:app --reload --port 8100
```

SQLite is the default local database. Set `DEVELOPER_DATABASE_URL` to a
PostgreSQL connection string before deployment.

## API

- `POST /internal/events`: trace/event ingestion
- `GET /admin/overview`: session, step, error, cost, and latency totals
- `GET /admin/traces`: recent sessions
- `GET /admin/traces/{traceId}`: ordered steps and raw replay events
- `GET /evaluations`: local evaluation console
- `GET /admin/evaluations`: import missing local pilot items and list them
- `GET /admin/evaluations/{id}`: annotation and available local analysis runs
- `PUT /admin/evaluations/{id}`: update gold and annotation with revision conflict detection
- `POST /admin/evaluations`: add a YouTube/Instagram URL as an unreviewed item
- `POST /admin/evaluations/{id}/runs`: submit a run to the Spring API
- `POST /admin/evaluations/{id}/runs/{runId}/refresh`: retrieve and save its latest status/result
- `PUT /admin/evaluations/{id}/reviews/{runId}`: save a human review for a run and gold revision

The console imports `evaluation/pilot_v1.json` and `evaluation/user_sources.json`
without overwriting later edits. Edits are stored in the developer database, not
written back to the original files or shared through Git. Existing results are
read from fixed `.runtime` directories, so they remain local. An empty STT or OCR
list means the selected run did not store that evidence; it does not prove
extraction failed. Runs use the existing asynchronous app analysis flow and do
not automatically score results. They persist in the developer database and
are refreshed explicitly in the UI. Spring must be running; override its URL
using `SAVEON_API_BASE_URL`. A submission timeout may mean the request was
accepted; inspect the app server before retrying. YouTube/Instagram access and
Gemini free-tier quota still apply.
The comparison page shows two selected runs side by side. Judgments and notes
are human-authored, not automatic semantic or factual checks. Changing the gold
annotation marks prior reviews stale; review edits are kept in the developer
database and are not committed through Git. Annotation updates also increment
the revision and consequently mark previous reviews stale.

The gold editor offers fields for target names, required facts, whole-video
facts and global steps. More detailed fields, such as target-specific steps,
optional facts and evidence timestamps, remain available in the advanced JSON
editor. Newly entered facts do not automatically acquire evidence timestamps;
review and add those before treating the item as a verified gold label.
This console is for local/internal use. Configure the developer token and
appropriate authentication and access controls before exposing it remotely.

Set the same `DEVELOPER_API_TOKEN` on this server and the AI server when the
ingestion endpoint is reachable outside localhost.
