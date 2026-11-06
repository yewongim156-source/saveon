# save:on Content Conflicts v1

Smart Collections v1 + Q&A v1 위에 적용하는 누적 패치입니다.

## 기능

같은 주제의 저장물에 서로 양립하기 어려운 정보가 있으면 홈에서 사용자에게 알려줍니다.

예:
- 올리브영 행사 시작일: 11월 4일 vs 11월 5일
- 같은 제품 가격: 29,000원 vs 39,000원
- 같은 매장 영업시간: 21시 종료 vs 22시 종료

## 탐지 방식

1. COMPLETED 저장물의 structuredAnalysis.claims 수집
2. 같은 엔티티/주제 + 같은 claim type인 주장끼리만 후보화
3. 8003 Agent가 실제 모순인지 보수적으로 판정
4. Agent가 꺼져도 DATE_TIME / PRICE / STATISTIC은 명시적 값이 다르면 rule fallback
5. 홈에서 충돌이 있을 때만 `확인이 필요한 정보` 섹션 표시
6. 서로 다른 두 저장물의 문장을 보여주고 원본 상세로 이동 가능

다른 지점/다른 기간/서로 보완되는 정보처럼 동시에 참일 수 있는 내용은 모순으로 잡지 않도록 프롬프트를 제한했습니다.

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_content_conflicts_v1.zip -d ~/Downloads/saveon
```

## 서버 재시작

8000:
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn main:app --reload --port 8000
```

8001:
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn interest_agent:app --reload --port 8001
```

8002:
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn action_agent:app --reload --port 8002
```

8003 (Q&A + Smart Collection naming + Conflict detection):
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn qna_agent:app --reload --port 8003
```

Spring:
```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

Expo:
```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

새 native dependency는 없어서 prebuild는 필요 없습니다.

## API 테스트

```bash
curl "http://localhost:8080/api/v1/content-conflicts?limit=6"
```

충돌이 없으면:
```json
[]
```

충돌이 있으면:
```json
[
  {
    "key":"...",
    "subject":"올리브영",
    "claimType":"DATE_TIME",
    "title":"올리브영 행사 시작 날짜가 달라요",
    "description":"한 저장물은 11월 4일, 다른 저장물은 11월 5일로 안내하고 있어요.",
    "severity":"WARN",
    "evidences":[
      {
        "contentId":12,
        "title":"...",
        "claimText":"행사는 11월 4일부터 시작합니다.",
        "value":"11월 4일"
      },
      {
        "contentId":18,
        "title":"...",
        "claimText":"올리브영 행사는 11월 5일부터 시작합니다.",
        "value":"11월 5일"
      }
    ],
    "source":"AGENT"
  }
]
```

## 현재 v1 범위

- Agent 비교: DATE_TIME / PRICE / LOCATION / STATISTIC / PRODUCT_PERFORMANCE / HEALTH_BEAUTY / TRAVEL_RULE / OTHER
- 규칙 fallback: DATE_TIME / PRICE / STATISTIC
- 최소 2개의 서로 다른 COMPLETED 저장물 필요
- 서로 공유되는 entity/entityDetails가 있어야 후보가 됩니다.
- 팀원의 factChecks / verificationStatus가 있으면 Agent 입력에 함께 전달합니다.
- 외부 웹 검색은 이 기능 자체에서 하지 않습니다. 기존 Fact Verification 결과만 참고합니다.

## 테스트 팁

실제 저장물에서 충돌이 없다면 API가 `[]`인 게 정상입니다.
기능 확인을 위해 억지로 잘못된 데이터를 추가하기보다,
실제로 동일 행사/가격/운영시간을 다르게 말하는 콘텐츠가 생겼을 때 탐지되는지 확인하는 것이 권장됩니다.
