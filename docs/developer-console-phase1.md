# Save:On Developer Console Phase 1

## Scope

Phase 1 builds the event and trace foundation required by the Monitor,
Evaluation, Cost, Prompt, and Agent pages. It intentionally does not include a
browser UI yet.

## Runtime flow

```text
AI request
  -> trace session
  -> tool/agent step events
  -> non-blocking in-memory queue
  -> POST developer-api/internal/events
  -> raw trace_events + materialized trace_sessions/pipeline_steps
  -> admin overview/list/detail queries
```

The AI request does not wait for the Developer API. Queue overflow or network
failure drops telemetry and prints a warning while the user analysis continues.

## Instrumented steps

- source download
- upload save
- speech-to-text
- frame sampling
- screen-text OCR
- visual classification
- content structuring agent
- one fact-verification agent step per claim
- verified-summary agent
- semantic embedding

## Privacy defaults

- source URLs are stored only as SHA-256 hashes;
- input and output summaries are truncated and depth-limited;
- raw video bytes are never sent;
- full transcripts and OCR contents are not included in current telemetry;
- the internal API can require a shared token.

## Stored records

- `trace_sessions`: request status, duration, total cost, error
- `pipeline_steps`: agent/tool identity, model, prompt version, latency, tokens,
  cost, safe input/output summaries, error
- `trace_events`: append-only raw events for timeline replay

## Phase 2 entry criteria

- traces can be ingested without blocking AI requests;
- duplicate events are idempotent;
- overview, list, and detail endpoints return trace data;
- agent and tool failures are independently visible;
- source URLs are not present in stored telemetry.
