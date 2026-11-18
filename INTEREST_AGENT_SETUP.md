# save:on Interest Synthesis Agent v1

## What this patch adds

This patch upgrades the existing structured content connection + bundle feature with a separate **Interest Synthesis Agent**.

Architecture:

```text
Core AI server (port 8000)
  - video analysis / STT / OCR / vision / structured metadata

Spring API (port 8080)
  - structured entity connections
  - rule-based content bundle
  - calls Interest Agent when bundle has 2+ contents

Interest Synthesis Agent (port 8001)
  - receives the already-built bundle
  - Gemini synthesizes recurring interests and key takeaways
  - in-memory cache avoids repeated Gemini calls for identical bundles

Mobile
  - shows AI synthesis at the top of the bundle
  - keeps categories/tags/keywords/related entities/highlights below it
```

The teammate's `ai/main.py` and existing `AiClient.java` are intentionally not modified.

## Safety / fallback behavior

If the Interest Agent is down, Gemini fails, or the request times out, Spring does **not** fail the bundle API. It returns the existing rule-based bundle as:

```json
"synthesis": {
  "source": "RULE_BASED",
  "summary": "...",
  "keyInterests": [],
  "takeaways": []
}
```

When the agent succeeds:

```json
"synthesis": {
  "source": "AGENT",
  "summary": "...",
  "keyInterests": ["..."],
  "takeaways": ["..."]
}
```

## Apply patch

Run this only on the integration/test branch where the structured connection and bundle v1 already work.

```bash
cd ~/Downloads/saveon
git branch --show-current
unzip -o ~/Downloads/saveon_interest_agent_v1.zip -d ~/Downloads/saveon
```

## Start services

### 1. Existing core AI server — port 8000

```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn main:app --reload --port 8000
```

### 2. New Interest Synthesis Agent — port 8001

Open another terminal:

```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn interest_agent:app --reload --port 8001
```

Health check:

```bash
curl http://localhost:8001/health
```

Expected shape:

```json
{
  "status": "ok",
  "service": "saveon-interest-agent",
  "version": "1.0.0",
  "model": "gemini-3.1-flash-lite"
}
```

The actual model follows `GEMINI_MODEL` in `ai/.env` when configured.

### 3. Spring — port 8080

Restart Spring after applying the patch:

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

No extra property is required. The default Interest Agent URL is:

```text
http://localhost:8001
```

If needed later, it can be overridden with:

```properties
saveon.interest-agent.base-url=http://localhost:8001
```

## Test with the existing 올리브영 bundle

```bash
curl "http://localhost:8080/api/v1/content-connections/bundle?type=BRAND&entity=%EC%98%AC%EB%A6%AC%EB%B8%8C%EC%98%81"
```

Check the new `synthesis` field.

Success example:

```json
{
  "entity": "올리브영",
  "type": "BRAND",
  "count": 2,
  "synthesis": {
    "source": "AGENT",
    "summary": "저장한 콘텐츠에서는 올리브영 블랙프라이데이와 할인 활용법이 반복적으로 나타나요...",
    "keyInterests": [
      "블랙프라이데이 할인",
      "올영세일 쇼핑팁",
      "쿠폰·선착순 혜택"
    ],
    "takeaways": [
      "대형 매장 방문과 쿠폰 활용법이 주요 쇼핑 팁으로 반복돼요.",
      "웰라쥬·토리든·메노킨이 함께 반복 등장해요."
    ]
  }
}
```

Exact wording will vary because Gemini generates the synthesis.

## Fallback test

Stop only the port 8001 Interest Agent and call the same bundle endpoint again.

The API should still return HTTP 200, with:

```json
"synthesis": {
  "source": "RULE_BASED",
  ...
}
```

That confirms the agent cannot break the existing bundle feature.

## Mobile test

Existing native code is not changed, so no prebuild is required.

```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

Open a connection such as `올리브영`.

Expected order:

```text
관심 정보 묶음
→ Interest Synthesis Agent
   - AI 통합 badge
   - synthesized summary
   - 반복 관심
   - 통합 핵심
→ 주요 카테고리
→ 공통 관심
→ 공통 키워드
→ 함께 반복된 정보
→ 저장된 정보 요약
→ 관련 콘텐츠
```

## Cache

Identical bundle inputs are cached in memory by the Interest Agent for 30 minutes by default, so repeatedly opening the same bundle does not repeatedly call Gemini.

Optional environment variables:

```text
INTEREST_AGENT_CACHE_TTL_SECONDS=1800
INTEREST_AGENT_CACHE_MAX_ITEMS=128
```

The cache resets when the Interest Agent process restarts.
