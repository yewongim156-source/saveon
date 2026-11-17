# Save:on Collection Compare + Grounded External Verification v1

## 방향성

비교의 중심은 저장한 릴스/숏츠입니다.

1. 같은 Smart Collection의 저장물 2~8개를 비교합니다.
2. 비교 내용 자체는 저장된 콘텐츠만 사용합니다.
3. AI가 객관적으로 외부 확인 가치가 있는 항목을 최대 3개 고릅니다.
4. 가격/용량/위치/영업시간/행사 날짜/공식 스펙 등만 Google Search grounding으로 자동 확인합니다.
5. 외부 근거가 없으면 추측하지 않고 `확인 가능한 근거 부족`으로 표시합니다.

주관적 리뷰(맛, 예쁨, 분위기, 발림성 선호 등)는 외부 검색으로 우열을 만들지 않습니다.

## 추가 API

Spring:

`POST /api/v1/collection-comparisons`

예시:

```json
{
  "collectionTitle": "뷰티 쇼핑 꿀팁",
  "contentIds": [12, 13, 17, 18]
}
```

8003 Q&A Agent:

`POST /collections/compare`

## UI

스마트 컬렉션 상세에서:

`저장물 비교하기`

버튼이 추가됩니다.

결과는 두 구역으로 분리됩니다.

### 저장한 콘텐츠 기준

- 저장물별 공통점/차이점
- 각 값의 저장물 근거
- 정보가 없으면 `저장한 콘텐츠에서 확인되지 않음`

### 외부 근거로 자동 확인

- 객관적인 항목만 자동 검증
- 외부 확인 상태:
  - `외부 근거와 일치`
  - `현재 정보로 업데이트`
  - `외부 정보와 다름`
  - `확인 가능한 근거 부족`
- 실제 grounding source 링크 표시

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_collection_compare_grounded_v1.zip -d ~/Downloads/saveon
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

8000/8001/8002는 켜져 있으면 재시작할 필요 없습니다.

## 테스트

1. `모아보기`에서 저장물이 2개 이상 있는 스마트 컬렉션을 엽니다.
2. `저장물 비교하기`를 누릅니다.
3. 저장물 기반 비교가 먼저 나오는지 확인합니다.
4. 외부 확인 항목이 있을 경우 하단 `외부 근거로 자동 확인`을 확인합니다.
5. 출처를 눌러 실제 웹 근거가 열리는지 확인합니다.

외부 확인이 0건인 것도 정상입니다.
비교할 객관적 항목이 없으면 릴스/숏츠 기반 비교만 표시합니다.
