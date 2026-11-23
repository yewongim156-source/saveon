# SAVEON evaluation web build (work in progress)

This branch prepares an **evaluation-only web frontend** while preserving the iOS app.

## Local web smoke test

From the repository root:

```sh
cd mobile
npm install
npx expo start --web
```

Test that the page renders in a desktop browser and a mobile browser. The iOS Share Extension is not available on the web: paste a Reels/Shorts URL in the app instead.

## Static web build

```sh
cd mobile
npm run build:web
```

Expo exports the static site to `mobile/dist`. This does **not** deploy the AI or API servers.

## Backend connection

The frontend reads `EXPO_PUBLIC_API_BASE_URL` from `mobile/src/lib/api.ts`; if unset, it falls back to `http://localhost:8080/api/v1`.

Example for **local development only**:

```sh
EXPO_PUBLIC_API_BASE_URL=http://localhost:8080/api/v1 npx expo start --web
```

For a public site, use an HTTPS backend URL and configure CORS for the deployed frontend's origin. Browser requests to local `localhost` refer to the **visitor's device**, not the developer's machine.

## Shared evaluation-code setup

The web branch's `src/lib/api.ts` requests a shared evaluation code **only** if built with `EXPO_PUBLIC_EVALUATION_MODE=true`. The visitor types the code; it is stored in browser session storage, never embedded in the static bundle. The server must have the matching `SAVEON_EVALUATION_ACCESS_KEY` configured in Render.

Set the public Vercel build variables:

- `EXPO_PUBLIC_EVALUATION_MODE=true`
- `EXPO_PUBLIC_API_BASE_URL=https://YOUR-RENDER-API.onrender.com/api/v1`

Redeploy after these variables are set. Do not set the server's secret code in Vercel.

This is a **shared** evaluation database. Participants can see one another's saved content and should be told to use only public, nonsensitive videos. The current gate is not per-student authorization.

## Critical safety checklist before publishing

**Do not publish a live evaluation site yet.** A shared-code access guard exists on the web branch but there is no per-student data isolation and expensive-request rate limiting is still needed. A public evaluation site needs at least:

- Student isolation or an explicitly shared, disposable evaluation dataset with informed consent.
- Authentication/access control and restricted CORS; rate limiting for expensive analysis endpoints.
- API keys and database credentials only on the server, never in frontend `EXPO_PUBLIC_*` variables.
- Public HTTPS hosting for the API, AI worker, database, and media with appropriate storage controls.
- Hard quotas and a queue for Whisper/EasyOCR/CLIP/Gemini processing.
- Compatibility checks for upload, calendar, external navigation, and error dialogs in browsers.
- Verification that external short-form video retrieval is allowed and works from the hosting provider.

A free web host such as Vercel hosts only the exported frontend; running multimodal AI analysis continuously requires separate backend resources. No hosting or paid resources are provisioned by this branch.
