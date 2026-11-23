# SAVEON free backend deployment preparation

This is a **preparation**, not a complete deployment. No credentials are committed. The iOS app continues to work with its local defaults.

## Prepared on feature/web-evaluation-20261123

- `api/Dockerfile`: Java 21 multi-stage API build, suitable for Render Docker deployment.
- `application.properties`: environment overrides for DB, Spring port, and AI host.
- Local defaults remain unchanged for existing development workflows.

## Hosting proposal (no payment method)

- Frontend: existing Vercel Hobby app (web export is working).
- Java API: Render Free web service using `api` as the root directory and `api/Dockerfile` as the Dockerfile path.
- DB: Neon Free PostgreSQL, with `CREATE EXTENSION IF NOT EXISTS vector;` applied before JPA schema creation.

Neon connection information belongs in **Render dashboard environment variables**, never in GitHub or a public website.

### Java API environment variables

- `JDBC_DATABASE_URL=jdbc:postgresql://YOUR_HOST/YOUR_DB?sslmode=require`
- `DB_USERNAME=YOUR_NEON_USER`
- `DB_PASSWORD=YOUR_NEON_PASSWORD`
- `JPA_SHOW_SQL=false`
- `PORT` is provided by Render.
- `SAVEON_AI_BASE_URL` must point to an actual deployed, accessible HTTPS FastAPI service. **Without it, the Spring API cannot analyze newly submitted videos.**

**Do not share DB credentials or AI keys in chat, screenshots, or frontend `EXPO_PUBLIC_*` values.**

## Shared evaluation access gate (web branch only)

`EvaluationAccessFilter` requires a visitor-entered code for all `/api/v1/**` routes when hosted on Render or when `SAVEON_EVALUATION_REQUIRE_KEY=true`. If the code is absent on Render, it **fails closed** with 503 rather than exposing the API. The liveness endpoint `/healthz` remains public.

Set these Render server-side environment variables:

- `SAVEON_EVALUATION_REQUIRE_KEY=true`
- `SAVEON_EVALUATION_ACCESS_KEY=<YOUR_RANDOM_SHARED_CODE>` (keep private; never put it in Vercel)
- `SAVEON_EVALUATION_ALLOWED_ORIGIN=https://saveon-mobile.vercel.app`

Use a random, hard-to-guess code. Deliver it to a small invited evaluation group separately from the public web URL. It is a **shared evaluation room**, not individual accounts; all participants see the same database. Tell participants to use only public, non-sensitive content, and use a fresh, disposable database.

Set the following Vercel **frontend build** environment variables and redeploy after the Render API has a working HTTPS URL:

- `EXPO_PUBLIC_API_BASE_URL=https://YOUR-RENDER-API.onrender.com/api/v1`
- `EXPO_PUBLIC_EVALUATION_MODE=true`

The browser asks participants to type the evaluation code at first load and sends it as a request header. Do **not** put `SAVEON_EVALUATION_ACCESS_KEY` in any `EXPO_PUBLIC_*` variable.

**Before distributing publicly**, run a build/test, audit access restrictions, add per-visitor AI rate limits and verify the separate AI server works. The shared-code gate alone does not isolate student data.

## Direct Gemini analysis in the evaluation API

The web branch now contains `GeminiLiteService`, a **development/evaluation-only** direct Gemini path in Spring Boot. This replaces the `/analyze` and `/embed` calls to local FastAPI **only when** `SAVEON_AI_MODE=gemini-lite`. It does not deploy the complete original STT/OCR/CLIP pipeline and does not implement every agent endpoint.

**Before enabling**, verify the exact Google AI Studio project and model show **Free Tier** and that **no billing account is linked**. If no unbilled free key is available, do not enable this mode. Never place this key in GitHub, Vercel or `EXPO_PUBLIC_*` variables.

In Render **server-side** environment variables:

- `SAVEON_AI_MODE=gemini-lite`
- `GEMINI_API_KEY=<your unbilled FREE tier API key>` (secret)
- `SAVEON_LITE_MODEL=gemini-3.5-flash-lite` (currently lists free-tier input/output; verify eligibility)
- `SAVEON_LITE_DAILY_ANALYSES=20`
- `SAVEON_EVALUATION_DAILY_SAVES=20`

`SAVEON_AI_BASE_URL` is unused for `AiClient.analyze` and `AiClient.embed` in this mode, but **some other Agent clients still rely on the original FastAPI service**, so they may return fallbacks/errors. Do not claim full feature parity.

This mode sends **public YouTube URL** to the Gemini Interactions API for video analysis and uses text embedding `gemini-embedding-001` (768 dimensions). For public Instagram Reels, the API container downloads video and audio with yt-dlp, merges them with FFmpeg, and sends an MP4 up to 8 MiB to Gemini. Reels whose media Instagram does not serve to the downloader fail analysis. File uploads are disabled. The access filter rejects `POST /api/v1/contents/upload` when hosted. Gemini free quotas and the instance-local per-day limit can stop analysis; the counter can reset after a free service restart. **Unbilled Free Tier project** is the relevant protection against unexpected Gemini charges, not an in-memory counter.

After adding env variables, **manually deploy the latest `feature/web-evaluation-20261123` commit** (Auto-Deploy is off), confirm `/healthz` and test one public YouTube Short and one public Instagram Reel. Rendering of structured analyses may be less complete than the original multimodal pipeline.

For local confirmation without secrets, run:

```sh
cd api
./gradlew test --no-daemon
```

The new tests check URL restrictions and fail-closed behavior, not live Google API service availability. No remote build/test has been run as part of creating these commits.

## Critical blockers

1. **Do not publicize a live API yet.** The web branch has a shared evaluation-code gate and origin check but does not isolate student data. Use a disposable DB with informed participant consent, plus rate limiting before inviting users.
2. Render Free is 512 MB RAM and sleeps after inactivity; Java Spring Boot + JPA may need memory tuning, and cold starts are expected.
3. Render does NOT supply a free multimodal AI runtime capable of running SAVEON's unchanged local `faster-whisper`, `EasyOCR`, `torch`, `CLIP`, and video downloader pipeline.
4. The iOS/Android Share Extension and native calendar/media-picker behaviors need browser-specific fallbacks.
5. If Gemini/Youtube-URL input replaces the local models for an evaluation build, that is an **implementation change**, and must be labeled accordingly. YouTube/Instagram rights and access constraints remain.
6. Render free Postgres expires after 30 days. Use Neon Free if a persistent evaluation DB is needed, within its quotas.
7. Review the database schema, model import side effects, storage, and health endpoints before deploying.

Nothing here creates any billed service; do not select paid tiers or enter credit-card information to complete this plan.
