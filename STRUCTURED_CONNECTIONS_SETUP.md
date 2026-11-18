# save:on 구조화 기반 콘텐츠 연결 v1

이 패치는 팀원의 `codex/rag-structured-search` 구조화 기능이 `main`에 합쳐진 뒤 적용하는 것을 전제로 합니다.

## 연결 기준

`contents.structured_analysis`에 저장된 `entityDetails`를 사용합니다.

```json
{
  "entityDetails": [
    {
      "name": "성수역",
      "type": "PLACE",
      "confidence": 0.92
    }
  ]
}
```

아래 조건을 모두 만족해야 홈의 연결 카드에 표시됩니다.

- 콘텐츠 상태 `COMPLETED`
- 타입: `PLACE`, `PRODUCT`, `BRAND`, `PERSON`, `SERVICE`
- confidence `0.65` 이상
- 동일한 `type + 정규화된 name`이 서로 다른 콘텐츠 2개 이상에서 등장

동일 콘텐츠 내부 중복은 한 번만 계산합니다.

## 새 API

반복 연결 조회:

```text
GET /api/v1/content-connections?limit=8
GET /api/v1/content-connections?type=PLACE&limit=8
```

응답 예시:

```json
[
  {
    "entity": "성수역",
    "type": "PLACE",
    "count": 3,
    "confidence": 0.94
  }
]
```

연결된 콘텐츠 조회:

```text
GET /api/v1/content-connections/contents?type=PLACE&entity=성수역
```

## 충돌 최소화

백엔드의 기존 `ContentRepository`, `ContentService`, `ContentController`는 수정하지 않습니다.
새 클래스를 추가해서 연결 기능을 독립시켰습니다.

추가 파일:

- `ContentConnectionController.java`
- `ContentConnectionService.java`
- `ContentConnectionResponse.java`

모바일 수정:

- `mobile/App.tsx`
- `mobile/src/lib/api.ts`

## 적용 시점 주의

현재 `main`의 `Content`에는 `getStructuredAnalysis()`가 아직 없으므로 팀원 브랜치가 merge되기 전에 이 패치를 적용하면 Spring 컴파일이 실패합니다.

## merge 후 적용

프로젝트 루트에서:

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_structured_connections_v1.zip -d .
```

그다음 Spring 재시작:

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

API 확인:

```bash
curl "http://localhost:8080/api/v1/content-connections?limit=8"
```

모바일은 네이티브 설정을 바꾸지 않았으므로 `expo prebuild --clean`은 필요 없습니다.

```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

## 화면 동작

홈 `반복해서 등장한 정보`:

```text
[장소] 성수역
3개 콘텐츠에서 반복
관련 콘텐츠 보기 >
```

카드를 누르면 기존 검색 화면을 활용해:

```text
성수역 관련 콘텐츠
3개 연결된 콘텐츠
```

처럼 해당 구조화 엔티티가 실제로 포함된 콘텐츠만 표시합니다.
