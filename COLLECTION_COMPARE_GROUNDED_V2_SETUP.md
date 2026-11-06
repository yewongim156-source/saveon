# Save:on Collection Compare v2

## 핵심 원칙

비교 기능의 주인공은 외부 검색이 아니라 **사용자가 저장한 릴스/숏츠 사이의 관계**입니다.

### 비교가 제안되는 조건
- 같은 PLACE / PRODUCT / BRAND / SERVICE 엔티티가
  서로 다른 저장물 2개 이상에서 반복 등장
- 신뢰도 0.45 이상 entityDetails 우선
- 비교 가능한 반복 엔티티가 없으면:
  `비교보다 모아보기가 더 잘 맞아요`

즉, 모든 Smart Collection에 비교를 억지로 적용하지 않습니다.

## 결과 구조

### 1. 엇갈리는 점
가장 중요한 비교 가치입니다.

서로 다른 영상이 같은 주제에 대해 다르게 말할 때 표시합니다.

예:
- 영상 A: `밀착력이 좋다`
- 영상 C: `들뜸이 있다`

어느 쪽이 맞다고 결론내리지 않습니다.

### 2. 공통점
2개 이상의 서로 다른 저장 영상이 공통으로 언급한 내용입니다.

### 3. 한 영상에만 나온 정보
다른 영상에는 없고 한 영상에서만 확인되는 유용한 내용입니다.

## 근거 표시

모든 비교 결과는:
- contentId
- 영상 제목
- 근거 문장

과 연결됩니다.

`timestampSeconds` 필드도 준비되어 있지만,
현재 Save:on 분석 데이터에는 STT 구간 타임스탬프가 저장되지 않으므로
**실제 timestamp가 있는 경우에만 표시**합니다.

타임스탬프를 임의로 생성하지 않습니다.

## 외부 확인 Trigger

외부 검색은 AI가 임의로 고르지 않습니다.

허용 필드:
- PRICE
- CAPACITY
- SIZE
- RELEASE_DATE
- EVENT_PERIOD
- OFFICIAL_NAME
- LOCATION
- OPENING_HOURS
- CLOSED_DAYS

그리고 반드시:
1. 서로 다른 저장 영상 2개 이상에서 언급되고
2. 명시적인 값이 2개 이상이며
3. 값이 서로 달라야 합니다.

예:
- 영상 A: 18,000원
- 영상 B: 22,000원

=> 외부 공식 가격 확인 실행

한 영상에서만 가격을 언급하면 자동 외부 검색하지 않습니다.

주관적 정보:
- 발색
- 사용감
- 맛
- 분위기
- 예쁨
- 개인 후기

는 외부 확인하지 않습니다.

## 외부 정보 표시

저장 영상 정보는 절대 덮어쓰지 않습니다.

화면에 병렬 표시:
- 저장물에서 나온 값
- 현재 외부 확인 값
- 설명
- 확인 시점
- 출처 링크

현재 값이 다르더라도
`영상이 틀렸다`고 바로 단정하지 않습니다.
가격/영업시간 등은 영상 게시 이후 변경됐을 수 있습니다.

## 추천 정책

Save:on은:
`그래서 A를 사세요`
`B 식당을 가세요`

처럼 최종 선택을 대신하지 않습니다.

저장한 영상의:
- 공통점
- 엇갈림
- 단독 정보
- 객관 정보 현재 상태

를 판단 재료로 정리합니다.

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_collection_compare_grounded_v2.zip -d ~/Downloads/saveon
```

## 재시작

8003:
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

## 테스트 포인트

1. 같은 주요 정보가 반복되는 Smart Collection
2. `저장물 비교하기`
3. `엇갈리는 점`이 최상단에 나타나는지
4. 각 결과에 근거 영상이 붙는지
5. 가격/날짜 등 객관 값이 서로 다를 때만 외부 확인이 나오는지
6. 외부 결과에 확인 시점과 출처가 보이는지
7. 반복 entity가 없는 컬렉션은 비교 대신 모아보기를 안내하는지
