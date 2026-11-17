# save:on Smart Collections v1

Q&A v1 위에 적용하는 누적 패치입니다.

## 기능

저장물이 2개 이상 쌓이면 다음 신호를 이용해 자동 컬렉션 후보를 만듭니다.

- structuredAnalysis.tags
- entities / entityDetails
- keywords
- categories
- semantic search 결과

후보별로 semantic search를 사용해 비슷한 저장물을 확장하고,
멤버가 거의 같은 컬렉션은 Jaccard similarity로 중복 제거합니다.

예:
- 성수 카페
- 올리브영 할인
- 나트랑 여행
- 머신러닝 공부

8003 Q&A Agent가 실행 중이면 Gemini가 사용자가 보기 좋은
컬렉션 이름/설명을 생성합니다.
8003이 꺼져 있어도 rule-based 이름으로 기능은 동작합니다.

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_smart_collections_v1.zip -d ~/Downloads/saveon
```

## 서버

기존 서버를 그대로 사용합니다.

8000 분석/embedding:
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn main:app --reload --port 8000
```

8001 Interest:
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn interest_agent:app --reload --port 8001
```

8002 Action:
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn action_agent:app --reload --port 8002
```

8003 Q&A + Smart Collection naming:
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

새 native dependency는 없으므로 prebuild는 필요 없습니다.

## API 테스트

```bash
curl "http://localhost:8080/api/v1/smart-collections?limit=6"
```

예상 형태:
```json
[
  {
    "key":"...",
    "seed":"성수",
    "title":"성수 카페",
    "description":"성수에서 방문할 만한 카페 관련 저장물이 모여 있어요.",
    "count":3,
    "categories":["음식/레시피","장소/여행"],
    "commonKeywords":["성수카페","베이커리"],
    "commonEntities":["성수동","어니언"],
    "contents":[...],
    "source":"AGENT"
  }
]
```

## 앱 테스트

홈에서:
`자동으로 묶인 주제`

컬렉션 카드를 누르면:
- 컬렉션 설명
- 카테고리
- 관련 저장물 목록
을 볼 수 있습니다.

## 주의

- 컬렉션은 저장물 2개 이상에서 반복되는 seed가 있어야 생성됩니다.
- 기존 저장물에 embedding이 없거나 8000이 꺼져 있어도 metadata fallback으로 컬렉션은 생성될 수 있습니다.
- semantic search가 정상일 때 더 넓은 표현의 비슷한 저장물까지 묶습니다.
- 컬렉션은 DB에 별도 저장하지 않고 현재 저장물 기준으로 동적 생성합니다. 따라서 사용자 수정/Canonical 보정이 반영되면 다음 조회부터 컬렉션도 자연스럽게 달라집니다.
