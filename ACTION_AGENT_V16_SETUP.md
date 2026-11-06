# save:on Action Agent v1.6 — Single Content Action

이 패치는 v1.5를 포함한 누적 패치입니다.
**v1.5를 아직 적용하지 않았어도 v1.6 ZIP만 적용하면 됩니다.**

## 해결한 문제

이전 구조:
- 같은 entity가 2개 이상 콘텐츠에서 반복
- content bundle 생성
- bundle 화면에서만 Action Agent 실행

문제:
- "성수동 OO카페" 영상 하나만 저장한 경우
- PLACE가 정확히 추출되어도 연결 묶음이 없어서 지도 버튼이 안 뜸

v1.6:
- SINGLE_CONTENT
- CONTENT_BUNDLE

두 입력을 같은 Action Agent가 처리합니다.

```text
AI 분석
├─ 단일 콘텐츠 상세
│  └─ Action Agent → 즉시 행동
│
└─ 반복 entity 연결
   └─ bundle
      └─ Action Agent → 통합 행동
```

## 단일 콘텐츠 행동 조건

### PLACE
`structuredAnalysis.entityDetails`에:
- type=PLACE
- confidence >= 0.65

이면 지도 검색 제안 가능.

예:
```json
{
  "name": "어니언 성수",
  "type": "PLACE",
  "confidence": 0.96
}
```

→ 네이버지도 / 카카오맵

### PRODUCT / BRAND
confidence >= 0.65인 PRODUCT 또는 BRAND가 있으면:
- 비교 검색
- 관련 정보 검색

### DATE_TIME
`structuredAnalysis.claims`에:
- verifiable=true
- type=DATE_TIME
- confidence >= 0.65

이면 캘린더 후보 생성 가능.

### RECIPE / HOW_TO
`contentType`이 RECIPE/HOW_TO 또는 카테고리가 음식/레시피면:
- 체크리스트 생성 가능

## API

기존 bundle:
```http
POST /api/v1/content-actions/plan
```

새 단일 콘텐츠:
```http
POST /api/v1/content-actions/plan/content/{contentId}
```

예:
```bash
curl -X POST \
  "http://localhost:8080/api/v1/content-actions/plan/content/13"
```

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_action_agent_v16.zip -d ~/Downloads/saveon
```

## expo-calendar

v1.5에서 아직 설치하지 않았다면:

```bash
cd ~/Downloads/saveon/mobile
npx expo install expo-calendar
npx expo prebuild --clean
npx expo run:ios
```

이미 v1.5 적용 후 `expo-calendar`로 native rebuild까지 했다면
이번 v1.6 때문에 다시 prebuild할 필요는 없습니다.

평소 실행:
```bash
npx expo start --dev-client -c
```

## Action Agent

```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn action_agent:app --reload --port 8002
```

health:
```bash
curl http://localhost:8002/health
```

응답에:
```json
{
  "supportedContexts": [
    "SINGLE_CONTENT",
    "CONTENT_BUNDLE"
  ]
}
```

가 있어야 합니다.

## Spring

기존 8080 Spring을 먼저 종료한 뒤:

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

## 테스트

### 1. 기존 콘텐츠 ID로 직접 확인

예:
```bash
curl -X POST \
  "http://localhost:8080/api/v1/content-actions/plan/content/13"
```

`source: AGENT`가 나오면 단일 콘텐츠 Agent 성공.

### 2. 앱

보관함 → 콘텐츠 하나 → 상세화면

상단 AI 요약 바로 아래에:
- Action Agent
- 지도
- 비교
- 캘린더
- 체크리스트
- 웹 검색

중 해당 콘텐츠에 실제 근거가 있는 것만 표시됩니다.

**관련 콘텐츠가 2개 이상일 필요가 없습니다.**

## 추가 UI 수정

v1.5에서:
- 캘린더/체크리스트 카드에 빈 `“”`가 보일 수 있던 문제

v1.6:
- 검색 → 검색어
- 캘린더 → `YYYY-MM-DD · 종일 일정`
- 체크리스트 → `N개 체크 항목`

으로 표시합니다.

## fallback

Action Agent(:8002)가 실패해도:

단일 콘텐츠:
- PLACE → 지도
- PRODUCT/BRAND → 비교
- 그 외 → 웹 검색

처럼 structured entity를 기반으로 RULE_BASED 기본 행동이 표시됩니다.

bundle fallback도 기존대로 유지됩니다.
