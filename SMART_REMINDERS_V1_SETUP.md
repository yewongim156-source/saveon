# save:on 스마트 리마인더 v1

## 기능
`모아보기`에 **다시 볼 타이밍** 섹션을 추가합니다.

현재 버전은 OS 푸시 알림을 바로 보내지 않습니다. 먼저 저장 이력을 바탕으로
"지금 다시 보기 좋은 저장물"을 추천하고, 추천 정확도를 검증하는 단계입니다.

### 추천 근거
- `DATE_TIME` 구조화 claim이 있는 콘텐츠 → 날짜 확인
- 세일/할인/쿠폰/블랙프라이데이/행사/이벤트/팝업 등 → 놓치기 전에 다시 보기
- 장소/여행 카테고리, 호텔/숙소/맛집/카페/웨이팅 등 → 외출·여행 전에 다시 보기
- 최근 30일 동안 반복된 keyword/entity → 반복 관심사 다시 보기

추천 카드를 누르면 해당 저장물 상세로 이동합니다. 상세 화면의 기존 `바로 활용하기`
기능을 통해 지도/캘린더/검색 등으로 이어갈 수 있습니다.

## API

```text
GET /api/v1/smart-reminders?limit=6
```

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_smart_reminders_v1.zip -d ~/Downloads/saveon
```

## 재시작

Spring Java 파일이 추가됐으므로 Spring Boot 재시작:

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

모바일도 재시작:

```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

8000 / 8001 / 8002 / 8003은 기존에 켜져 있으면 재시작할 필요 없습니다.

## API 단독 테스트

```bash
curl "http://localhost:8080/api/v1/smart-reminders?limit=6"
```

예시:

```json
[
  {
    "key": "EVENT_CHECK:12",
    "type": "EVENT_CHECK",
    "title": "혜택이나 행사가 끝나기 전에 다시 볼까요?",
    "description": "올리브영 블랙프라이데이...에 세일·이벤트 관련 정보가 있어요.",
    "badge": "놓치기 전에",
    "contentId": 12,
    "contentTitle": "올리브영 블랙프라이데이 알차게 쇼핑하는 꿀팁",
    "sourceUrl": "...",
    "evidence": ["행사·혜택 관련 표현: 블랙프라이데이", "최근 반복 저장: 올리브영"],
    "score": 7
  }
]
```

## 노출 위치

`모아보기 > 최근 관심 변화` 아래에 `다시 볼 타이밍`이 표시됩니다.
추천할 만한 근거가 없으면 섹션 자체를 숨깁니다.

## 다음 버전 후보
v2에서는 추천 카드마다 사용자가 직접 `알림 켜기`를 선택한 항목에 한해 Expo Notifications로 실제 로컬 알림을 등록할 수 있습니다.
