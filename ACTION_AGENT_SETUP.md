# Save:on Action Agent v1

## 목표
Interest Synthesis Agent가 만든 관심 묶음을 실제 후속 행동으로 연결한다.

v1에서 Action Agent는 행동을 직접 실행하지 않는다. 다음 세 종류 중 적절한 행동과 검색어만 구조화해서 반환한다.

- `MAP_SEARCH`: 장소를 지도에서 검색
- `WEB_SEARCH`: 관련 최신 정보를 웹에서 검색
- `COMPARE_SEARCH`: 제품/브랜드 비교 정보를 웹에서 검색

앱만 허용된 행동 종류를 실제 URL로 변환한다. Agent가 임의 URL을 만들거나 임의 구매/예약/메시지를 실행하지 않는다.

## 서버 구조
- 기존 분석 AI: `8000`
- Interest Synthesis Agent: `8001`
- Action Agent: `8002`
- Spring API: `8080`

## 실행

```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn action_agent:app --reload --port 8002
```

Health:

```bash
curl http://localhost:8002/health
```

Spring은 재시작한다.

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

## 테스트
먼저 기존 bundle을 저장한다.

```bash
curl "http://localhost:8080/api/v1/content-connections/bundle?type=BRAND&entity=%EC%98%AC%EB%A6%AC%EB%B8%8C%EC%98%81" > /tmp/saveon-bundle.json
```

그 bundle을 Action API에 전달한다.

```bash
curl -X POST "http://localhost:8080/api/v1/content-actions/plan" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/saveon-bundle.json
```

정상적인 Agent 응답 예시:

```json
{
  "source": "AGENT",
  "actions": [
    {
      "kind": "COMPARE_SEARCH",
      "title": "할인 정보 비교하기",
      "description": "저장 콘텐츠에 반복된 세일 관심사를 기준으로 비교 정보를 검색해요.",
      "query": "올리브영 블랙프라이데이 할인 비교"
    }
  ]
}
```

Action Agent가 꺼져 있거나 Gemini가 실패해도 Spring이 `RULE_BASED` 행동을 반환한다.

## 모바일
네이티브 설정 변경은 없다.

```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

관심 정보 묶음에서 `Action Agent` 영역의 버튼을 누르면:
- 장소 → Google Maps 검색
- 일반 정보 → Google 웹 검색
- 제품/브랜드 → 비교 검색

으로 연결된다.

## 후속 단계
Calendar Action은 날짜 정규화가 안정된 뒤 별도 단계에서 추가하는 것이 안전하다.
