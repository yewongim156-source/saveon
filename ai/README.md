# Save:On AI server

FastAPI server for URL and uploaded-video analysis.

The AI server also provides:

- Gemini structured metadata with stable top-level categories, dynamic tags,
  typed entities, and verifiable claims;
- 768-dimensional Gemini embeddings through `POST /embed`;
- optional Google Search-grounded fact checking for up to three claims.

## YouTube URL pipeline

`POST /analyze` now accepts a public YouTube watch, Shorts, or `youtu.be`
URL. The server:

1. validates the host and rejects playlists/live streams;
2. reads metadata before download and checks the duration limit;
3. downloads temporary video and audio streams with `yt-dlp`;
4. runs Whisper, EasyOCR, and CLIP through `video_pipeline.py`;
5. returns title, summary, categories, keywords, and entities;
6. deletes the temporary media when the request finishes.

When YouTube does not expose a combined media file, video and audio are kept
separate during analysis. OpenCV reads the video while Whisper reads the audio,
so an external ffmpeg merge step is not required.

Private, login-required, age-restricted, region-restricted, and unavailable
videos are not supported. The MVP runs synchronously, so the Spring request
waits until analysis finishes.

## Configuration

| Environment variable | Default | Purpose |
| --- | ---: | --- |
| `YOUTUBE_MAX_DURATION_SECONDS` | `600` | Reject longer videos before download |
| `YOUTUBE_MAX_FILE_SIZE_MB` | `150` | Maximum downloaded media size |
| `WHISPER_MODEL` | `base` | faster-whisper model name |
| `CLIP_MODEL` | `openai/clip-vit-base-patch32` | Transformers CLIP model |
| `SAVEON_MODEL_CACHE_DIR` | `saveon/.runtime/model-cache` | Local cache for Whisper, EasyOCR, and CLIP model files |
| `GEMINI_API_KEY` | none | Gemini structuring, embedding, and grounding |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Structured content analysis model |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-2` | Semantic-search embedding model |
| `GEMINI_EMBEDDING_DIMENSIONS` | `768` | Must match the pgvector column |
| `GEMINI_REQUEST_TIMEOUT_MS` | `30000` | Per-request Gemini SDK timeout in milliseconds |
| `GEMINI_RETRY_ATTEMPTS` | `3` | Attempts for transient Gemini 5xx failures; quota errors are not retried |
| `FACT_CHECK_ENABLED` | `false` | Enable search-grounded claim verification |
| `GEMINI_VERIFIED_SUMMARY_MODEL` | `GEMINI_MODEL` | Rewrites the final summary from fact-check evidence |
| `MAX_FACT_CHECK_CLAIMS` | `3` | Maximum claims verified per content |
| `DEVELOPER_TELEMETRY_ENABLED` | `false` | Send non-blocking trace events to the Developer API |
| `DEVELOPER_API_URL` | `http://localhost:8100` | Internal observability server URL |
| `DEVELOPER_API_TOKEN` | none | Shared token for the internal ingestion endpoint |

## Run

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Run these commands from the `ai` directory. The first analysis downloads the
configured Whisper, OCR, and CLIP model files.

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` to enable structured
metadata and semantic embeddings. Fact checking stays disabled until
`FACT_CHECK_ENABLED=true` is set because it adds external search calls.

## Test

```bash
python -m unittest discover -s tests -v
```
