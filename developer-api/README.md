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

Set the same `DEVELOPER_API_TOKEN` on this server and the AI server when the
ingestion endpoint is reachable outside localhost.
