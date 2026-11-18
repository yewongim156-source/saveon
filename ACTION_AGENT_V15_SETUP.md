# save:on Action Agent v1.5

전제:
- `saveon_interest_agent_v1_fixed.zip`
- `saveon_action_agent_v1.zip`
가 적용되어 있고 Action Agent(:8002)까지 정상 동작하는 테스트 브랜치 기준 업그레이드입니다.

## 추가된 행동

### 1) PLACE → 네이버지도 / 카카오맵
Action Agent는 기존처럼 `MAP_SEARCH`를 반환합니다.
앱에서 버튼을 누르면 지도 선택창이 뜹니다.

- 네이버지도: `nmap://search` 우선, 실패 시 Naver Map web fallback
- 카카오맵: `kakaomap://search` 우선, 실패 시 Kakao Map mobile web fallback

### 2) DATE_TIME claim → 캘린더 추가
팀원의 `structuredAnalysis.claims` 중:
- `verifiable=true`
- `type=DATE_TIME`
- `confidence >= 0.65`

인 claim만 bundle의 `actionFacts`로 전달합니다.

Action Agent는 이 근거가 있을 때만 `CALENDAR_ADD`를 만들 수 있습니다.
시간이 명시되지 않으면 임의 시간을 만들지 않고 **종일 일정**으로 저장합니다.

### 3) RECIPE / HOW_TO → 체크리스트
`structuredAnalysis.contentType`이:
- `RECIPE`
- `HOW_TO`

이거나 카테고리가 `음식/레시피`일 때만 `CHECKLIST_CREATE`를 허용합니다.

체크 항목은 synthesis/highlights에 실제로 있는 내용만 사용하도록 프롬프트와 서버 검증을 넣었습니다.
앱 안에서 체크/해제가 가능합니다.

---

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_action_agent_v15.zip -d ~/Downloads/saveon
```

## expo-calendar 설치

SDK에 맞는 버전을 Expo가 자동으로 골라주도록 반드시 아래 명령을 사용합니다.

```bash
cd ~/Downloads/saveon/mobile
npx expo install expo-calendar
```

캘린더는 네이티브 모듈이라 개발 빌드를 한 번 다시 만들어야 합니다.

```bash
npx expo prebuild --clean
npx expo run:ios
```

이후 평소처럼:

```bash
npx expo start --dev-client -c
```

## 서버 재시작

Action Agent:

```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn action_agent:app --reload --port 8002
```

Spring:

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

기존 분석 Agent(:8000), Interest Agent(:8001)도 필요 시 그대로 켜둡니다.

## health

```bash
curl http://localhost:8002/health
```

`CALENDAR_ADD`, `CHECKLIST_CREATE`가 supportedActions에 추가되어야 합니다.

## bundle 확인

```bash
curl "http://localhost:8080/api/v1/content-connections/bundle?type=BRAND&entity=%EC%98%AC%EB%A6%AC%EB%B8%8C%EC%98%81"
```

이번 버전부터 응답에 아래가 추가됩니다.

```json
{
  "contentTypes": ["HOW_TO"],
  "actionFacts": [
    {
      "contentId": 13,
      "text": "11월 4일 올리브영 스페셜 드롭 이벤트가 진행된다.",
      "type": "DATE_TIME",
      "confidence": 0.95
    }
  ]
}
```

## Action Agent 테스트

```bash
curl "http://localhost:8080/api/v1/content-connections/bundle?type=BRAND&entity=%EC%98%AC%EB%A6%AC%EB%B8%8C%EC%98%81" > /tmp/saveon-bundle.json

curl -X POST "http://localhost:8080/api/v1/content-actions/plan" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/saveon-bundle.json
```

올리브영 테스트 데이터에는 `HOW_TO`와 `DATE_TIME` claim이 있으므로
Agent 판단에 따라 `CALENDAR_ADD` 또는 `CHECKLIST_CREATE`가 포함될 수 있습니다.
단, 최대 3개 행동만 선택하므로 둘 다 항상 나오는 것은 아닙니다.

## 안전장치

- 날짜 claim이 없으면 `CALENDAR_ADD` 제거
- 과거 날짜 / 잘못된 ISO 날짜 제거
- RECIPE/HOW_TO 근거가 없으면 `CHECKLIST_CREATE` 제거
- Agent 실패 시 기존 RULE_BASED 검색/지도 제안 유지
- RULE_BASED에서도 HOW_TO/RECIPE의 synthesis takeaways가 2개 이상이면 체크리스트 fallback 가능
- 캘린더는 사용자가 버튼을 눌렀을 때만 권한 요청 및 일정 생성
