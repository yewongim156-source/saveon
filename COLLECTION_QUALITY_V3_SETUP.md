# Save:on Collection Quality + Compare Recovery v3

이 패치는 스마트 컬렉션과 컬렉션 비교 백엔드 로직만 수정합니다.
모바일 UI, Smart Reminder, Analysis Stability, Q&A agent는 덮어쓰지 않습니다.

## 수정 1 — 잘못된 Smart Collection 멤버 제거

기존에는 semantic search 결과가 넓게 들어온 뒤 broad category까지 매칭 근거로 쓰여서,
`쿠션` 묶음에 전혀 관계없는 콘텐츠가 들어올 수 있었습니다.

v3에서는:
- category는 collection seed로 사용하지 않음
- `맛집 / 뷰티 / 기술 / 쇼핑 / 패션 ...` 같은 broad term은 seed 금지
- entity > keyword > tag 순으로 seed 신뢰도 부여
- semantic similarity만으로는 멤버가 될 수 없음
- entity/keyword/tag에 직접적인 metadata evidence가 있어야 포함
- 강한 공통 entity/keyword가 있으면 오래된 잘못된 category chip은 노출하지 않음
- structured entityDetails는 confidence >= 0.45인 주요 entity만 collection evidence로 사용

따라서 `환승연애` 같은 콘텐츠가 `클리오 쿠션` 그룹으로 끌려오는 현상을 줄입니다.

## 수정 2 — 비교 대상 recovery

기존 v2는 entity name exact match 의존도가 높아:
- `클리오`
- `클리오 킬커버 메쉬 블러 쿠션`
- OCR/이전 분석 결과

처럼 저장물별 entity 표현이 조금만 달라도 비교 불가가 될 수 있었습니다.

v3에서는:
1. structured entityDetails
2. top-level entities
3. title / summary / keywords의 반복 text anchor

순서로 비교 대상을 복구합니다.

`쿠션`, `리뷰`, `추천`, `영상` 같은 generic token은 fallback anchor에서 제외해
가능하면 `클리오`처럼 더 구체적인 반복 대상을 선택합니다.

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_collection_quality_v3.zip -d ~/Downloads/saveon
```

## 재시작

Spring만 재시작하면 됩니다.

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

8000/8001/8002/8003/Expo는 이번 패치 때문에 재시작할 필요 없습니다.

## 테스트

1. 앱에서 Smart Collection/검색 화면을 다시 열어 새 collection을 받아옵니다.
2. 기존 `맛집 쿠션`처럼 잘못 생성된 묶음이 없어지는지 확인합니다.
3. 클리오 쿠션 관련 저장물만 묶이는 collection을 엽니다.
4. `비교 다시 보기` 또는 `저장물 비교하기`를 누릅니다.
5. 더 이상 `같은 주요 정보가 2개 이상의 저장물에서 반복되지 않았어요`가 나오지 않는지 확인합니다.

주의: Smart Collection은 동적 계산이므로 DB migration은 필요 없습니다.
기존 분석 데이터가 조금 지저분해도 v3 로직이 최대한 걸러냅니다.
