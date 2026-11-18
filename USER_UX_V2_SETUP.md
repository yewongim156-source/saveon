# save:on User UX v2

이 패치는 `AI Quality & Learning v1` 적용 후 덮어쓰는 사용자 화면 리팩터링입니다.

## 목표

내부 구조는 그대로 유지하지만 사용자에게는 다음 용어를 노출하지 않습니다.

- Action Agent
- Interest Synthesis Agent
- Entity / 엔티티
- PLACE / BRAND / PRODUCT 같은 enum
- Validation / confidence
- STT / OCR / Vision
- Spring Boot / FastAPI
- CONNECTED CONTENTS 같은 개발자용 표현

## 바뀐 화면

### 홈
- `반복해서 등장한 정보` → `내가 자주 저장한 관심사`
- 사용자 저장물이 0개일 때 온보딩 카드 표시
- `CM` 로고 → `SO`
- 기술 중심 문구 대신 저장 → 정리 → 활용 흐름 설명

### 저장
- STT/OCR/Vision 설명 제거
- `앱을 나가도 내용 정리는 계속된다`는 사용자 이점 중심 안내
- 같은 URL을 다시 저장하려는 경우 기존 저장물로 이동 안내

### 보관함
- `서버에서 새로고침` → `새로고침`
- 빈 화면에 실제 다음 행동 안내

### 검색
- 키워드 검색과 semantic search를 한 검색창 뒤에서 자동 병합
- 사용자는 검색 방식 차이를 알 필요 없음
- `엔티티가 실제로 함께 추출...` 같은 내부 용어 제거

### 관련 저장물 / 묶음
- `Interest Synthesis Agent` → `저장한 내용 한눈에 보기`
- `관심 정보 묶음` → `내가 모은 정보`
- `공통 키워드` 영역 제거
- `반복 관심` → `자주 나온 주제`
- `통합 핵심` → `저장물에서 반복된 내용`

### 바로 활용하기
- `Action Agent` 이름 완전 제거
- 최대 3개만 표시
- 가장 중요한 첫 행동을 강조
- 지도 / 검색 / 비교 / 캘린더 / 체크리스트를 사용자 언어로 통일

### 상세
- 정상일 때 `AI 결과 검증` 카드 자체를 보여주지 않음
- 문제가 있을 때만 `확인이 필요한 정보가 있어요` 카드 표시
- 오류 코드/내부 타입은 숨김
- AI 요약과 저장된 정보를 별도 카드로 분리
- 사용자가 고칠 필요가 있는 부분만 `수정` 버튼으로 접근
- 키워드는 사용자 수정 화면에서 숨김
- 엔티티 → `저장된 주요 정보`
- PLACE → `장소`, BRAND → `브랜드` 등 한국어로 표시
- 실패한 저장물은 `다시 정리하기` 버튼 제공
- 분석 중에는 앱을 나가도 된다는 안내 표시

## Interest Synthesis 문체
Agent prompt도 함께 수정했습니다.

기존:
`대형 매장을 방문하여 특가를 확인하는 것이 좋습니다.`

변경 목표:
`저장한 콘텐츠에서는 대형 매장 방문과 선착순 특가 확인이 반복적으로 언급돼요.`

즉 추천/훈계가 아니라 사용자가 저장한 내용을 근거로 정리합니다.

# 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_user_ux_v2.zip -d ~/Downloads/saveon
```

모바일은 새 native dependency가 없으므로 prebuild가 필요 없습니다.

```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

Interest Agent 문체 변경도 확인하려면 8001 서버를 재시작하세요.

```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn interest_agent:app --reload --port 8001
```

Spring/분석/Action 서버는 기존 그대로 사용합니다.

# 권장 테스트

1. 홈
   - `내가 자주 저장한 관심사` 문구 확인
   - 저장물 0개일 경우 온보딩 확인

2. 검색
   - `성수 데이트 카페`처럼 자연어 검색
   - 정확한 키워드가 없어도 semantic 결과가 섞이는지 확인

3. 상세 정상 콘텐츠
   - `AI 결과 검증` 카드가 항상 노출되지 않는지 확인
   - `AI가 정리한 내용`, `저장된 정보`, `바로 활용하기` 순서 확인

4. 모순 콘텐츠
   - 내부 오류 코드 대신 `확인이 필요한 정보가 있어요` 카드가 뜨는지 확인

5. 수정
   - PLACE/BRAND 대신 `장소/브랜드`로 보이는지 확인
   - 키워드 수정란이 숨겨졌는지 확인

6. 실패 콘텐츠
   - `다시 정리하기` 버튼 확인

7. 관련 콘텐츠
   - Agent / entity / bundle 등의 내부 용어가 화면에 남아 있지 않은지 확인
