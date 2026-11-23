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

## Critical blockers

1. **Do not publicize a live API yet.** The current endpoints expose a shared list of saved contents and permit broad cross-origin requests. Implement student data segregation or a deliberately shared/disposable evaluation dataset and access control first, plus rate limiting.
2. Render Free is 512 MB RAM and sleeps after inactivity; Java Spring Boot + JPA may need memory tuning, and cold starts are expected.
3. Render does NOT supply a free multimodal AI runtime capable of running SAVEON's unchanged local `faster-whisper`, `EasyOCR`, `torch`, `CLIP`, and video downloader pipeline.
4. The iOS/Android Share Extension and native calendar/media-picker behaviors need browser-specific fallbacks.
5. If Gemini/Youtube-URL input replaces the local models for an evaluation build, that is an **implementation change**, and must be labeled accordingly. YouTube/Instagram rights and access constraints remain.
6. Render free Postgres expires after 30 days. Use Neon Free if a persistent evaluation DB is needed, within its quotas.
7. Review the database schema, model import side effects, storage, and health endpoints before deploying.

Nothing here creates any billed service; do not select paid tiers or enter credit-card information to complete this plan.
