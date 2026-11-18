# save:on 관심사 타임라인 v1

## 기능
`모아보기` 상단에 최근 저장 패턴 변화를 보여줍니다.

- 최근 7일 저장 수
- 이전 7일 저장 수
- 최근 30일 저장 수
- 카테고리 증가/감소
- 최근 7일에 새롭게 2회 이상 반복된 키워드/주요 정보
- 최근 30일 자주 저장한 관심사

AI 서버를 새로 추가하지 않습니다. Spring이 기존 저장 이력을 집계하므로 기존 실행 구조를 그대로 사용합니다.

## API

```text
GET /api/v1/interest-timeline
```

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_interest_timeline_v1.zip -d ~/Downloads/saveon
```

## 재시작
백엔드 Java 파일이 추가되므로 Spring Boot는 재시작해야 합니다.

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

모바일도 캐시를 비우고 다시 시작합니다.

```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

8000 / 8001 / 8002 / 8003은 이미 실행 중이면 재시작할 필요 없습니다.

## API 단독 확인

```bash
curl http://localhost:8080/api/v1/interest-timeline
```

정상 예시:

```json
{
  "recentDays": 7,
  "recentCount": 6,
  "previousCount": 3,
  "last30DaysCount": 12,
  "summary": "최근에는 뷰티/패션 관련 저장이 이전 7일보다 늘었어요.",
  "categoryTrends": [],
  "emergingInterests": [],
  "topInterests": []
}
```

## 참고
테스트 데이터가 모두 같은 날 생성됐다면 `이전 7일`은 0으로 표시될 수 있습니다. 오류가 아니라 실제 `createdAt` 기준 집계 결과입니다.
