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
- `POST /admin/evaluations/{id}/runs`: submit an evaluation-only run to the AI API
- `POST /admin/evaluations/{id}/runs/{runId}/refresh`: retrieve and save its latest status/result
- `PUT /admin/evaluations/{id}/reviews/{runId}`: save a human review for a run and gold revision

The console imports `evaluation/pilot_v1.json` and `evaluation/user_sources.json`
without overwriting later edits. Edits are stored in the developer database, not
written back to the original files or shared through Git. Existing results are
read from fixed `.runtime` directories, so they remain local. An empty STT or OCR
list means the selected run did not store that evidence; it does not prove
extraction failed. New evaluation-only runs call the same AI analysis endpoint
directly and never create a Spring content/library record. They persist in the
developer database and are refreshed explicitly in the UI; they are not
automatically scored. Set `SAVEON_AI_API_BASE_URL` if needed. Existing legacy
runs may still refer to Spring records. The in-process worker is not durable:
restarting the developer API mid-run can leave an unfinished status requiring
manual recovery. YouTube/Instagram access and Gemini free-tier quota still apply.
The comparison page shows two selected runs side by side. Judgments and notes
are human-authored, not automatic semantic or factual checks. Changing the gold
annotation marks prior reviews stale; review edits are kept in the developer
database and are not committed through Git. Annotation updates also increment
the revision and consequently mark previous reviews stale.

Evaluation can select `baseline` or `few_shot_v1`; the selected variant is
stored with the result. It does not change the app's default prompt. For an
apples-to-apples prompt experiment, `evaluation/compare_prompt_variants.py`
reuses the same saved STT/OCR evidence and writes separate local results; it
does not re-download video or add to the library. Demo examples are fictional
and must not be treated as ground truth. One run per variant is not proof of
improvement; review multiple independently labelled items.

## External reference scope

`WIKIPEDIA_REFERENCE_ENABLED` defaults to true. The AI pipeline may append a
single exactly matching Korean Wikipedia introductory reference for an
evidence-linked target when the content type is EDUCATIONAL. The source and
URL are included, and `BACKGROUND_NOT_VERIFIED` is recorded. This does not
verify the video's claims and is not used for product, health, price or place
verification. Missing matches and network failures leave the summary alone.
The public API requires a meaningful user agent and has rate limits; see
https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy.

The gold editor offers fields for target names, required facts, whole-video
facts and global steps. More detailed fields, such as target-specific steps,
optional facts and evidence timestamps, remain available in the advanced JSON
editor. Newly entered facts do not automatically acquire evidence timestamps;
review and add those before treating the item as a verified gold label.
This console is for local/internal use. Configure the developer token and
appropriate authentication and access controls before exposing it remotely.

Set the same `DEVELOPER_API_TOKEN` on this server and the AI server when the
ingestion endpoint is reachable outside localhost.
