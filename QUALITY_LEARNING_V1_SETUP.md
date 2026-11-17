# save:on AI Quality & Learning v1

이 ZIP은 `saveon_action_agent_v1.6.1` 위에 적용하는 누적 업그레이드입니다.

## 이번에 추가된 것

### 1. Validation Layer
단일 콘텐츠 상세 화면에서 AI 구조화 결과를 규칙 기반으로 검사합니다.

현재 규칙:
- confidence < 0.65 엔티티 → `LOW_CONFIDENCE_ENTITY`
- 같은 이름이 여러 타입으로 등장 → `ENTITY_TYPE_CONFLICT`
- 장소/여행인데 확실한 PLACE가 없음 → `CATEGORY_ENTITY_CONFLICT`
- 존재하지 않는 DATE_TIME 날짜 → `INVALID_DATE`
- Canonical DB와 현재 타입이 다름 → `CANONICAL_TYPE_CONFLICT`

API:
```http
GET /api/v1/content-quality/{contentId}
```

### 2. Action-gated confirmation
지도:
```text
지도 검색 직전
→ 장소명 미리보기
→ [장소 수정] [계속]
```

캘린더:
```text
일정 등록 직전
→ 제목 + 날짜 미리보기
→ [날짜 수정] [추가]
```

Action 단계에서 사용자가 값을 수정하면 Correction Log에 기록합니다.

### 3. 사용자 직접 AI 결과 수정
상세 화면:
```text
AI 결과 검증
[AI 결과 수정]
```

수정 가능한 값:
- 제목
- 요약
- 카테고리
- 키워드
- 엔티티 이름
- 엔티티 타입

수정 후에는 Content의 최종값 자체가 갱신되므로:
- 일반 검색
- 콘텐츠 연결
- Bundle
- Action Agent

가 수정된 값을 바로 사용합니다.

원래 AI 결과는 `ai_corrections` 테이블에 별도로 보존됩니다.

### 4. Correction Log
DB:
```text
ai_corrections
```

주요 오류 유형:
- WRONG_TITLE
- WRONG_SUMMARY
- CATEGORY_MISMATCH
- WRONG_KEYWORD
- MISSING_ENTITY
- ENTITY_NAME_ERROR
- ENTITY_TYPE_MISMATCH
- WRONG_DATE
- OTHER

통계:
```http
GET /api/v1/ai-corrections/stats
```

예:
```json
{
  "totalCorrections": 12,
  "errorTypes": {
    "ENTITY_TYPE_MISMATCH": 5,
    "WRONG_DATE": 3
  }
}
```

### 5. Canonical Entity DB
사용자가 엔티티를 수정해서 확정하면:
```text
canonical_entities
```
에 저장합니다.

예:
```text
어니언 성수 → PLACE
```

다음 영상에서 AI가 다시:
```text
어니언 성수 → BRAND
```
라고 분석해도 새 분석 저장 직전에 Canonical DB를 확인해서:
```text
어니언 성수 → PLACE
```
로 자동 보정합니다.

URL 분석과 영상 업로드 분석 둘 다 적용됩니다.

---

# 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_quality_learning_v1.zip -d ~/Downloads/saveon
```

DB는 기존 설정이:
```properties
spring.jpa.hibernate.ddl-auto=update
```
이므로 Spring 재시작 시 새 테이블/컬럼을 자동 생성합니다.

Spring 재시작:
```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

Action Agent는 기존 그대로:
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn action_agent:app --reload --port 8002
```

분석 서버:
```bash
python -m uvicorn main:app --reload --port 8000
```

Interest Agent를 사용하는 bundle 테스트라면:
```bash
python -m uvicorn interest_agent:app --reload --port 8001
```

모바일:
```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

이번 패치는 새로운 native dependency를 추가하지 않으므로
v1.5에서 expo-calendar native build를 이미 했다면
다시 `prebuild --clean` 할 필요 없습니다.

---

# 테스트 1: Validation Layer

예: content 14

```bash
curl http://localhost:8080/api/v1/content-quality/14
```

정상 예:
```json
{
  "valid": true,
  "requiresReview": false,
  "warnings": []
}
```

의심 결과가 있으면:
```json
{
  "valid": true,
  "requiresReview": true,
  "warnings": [
    {
      "type": "LOW_CONFIDENCE_ENTITY",
      "field": "entityDetails",
      "severity": "WARN",
      "message": "..."
    }
  ]
}
```

---

# 테스트 2: 사용자 수정

앱:
```text
보관함
→ 콘텐츠 상세
→ AI 결과 검증
→ AI 결과 수정
```

예:
```text
어니언 성수
BRAND
```

를:
```text
어니언 성수
PLACE
```

로 수정하고 저장.

저장 후:
- `사용자 수정됨` 배지
- Action Agent 재조회
- PLACE이면 지도 Action 생성 가능
- 연결 정보도 새 값으로 갱신

---

# 테스트 3: Correction 통계

```bash
curl http://localhost:8080/api/v1/ai-corrections/stats
```

수정 후 `ENTITY_TYPE_MISMATCH` 등이 증가해야 합니다.

특정 콘텐츠 기록:
```bash
curl http://localhost:8080/api/v1/ai-corrections/content/14
```

---

# 테스트 4: Action 직전 수정

지도 버튼:
```text
장소를 확인해줘
“어니언 성수”
[장소 수정] [계속]
```

장소 수정 후 지도 앱으로 이동하면:
- 수정값으로 지도 검색
- `ENTITY_NAME_ERROR` Correction Log 저장
- 수정한 장소명은 Canonical DB에도 저장

캘린더:
```text
일정을 확인해줘
올리브영 스페셜 드롭
2026-11-04 · 종일
[날짜 수정] [추가]
```

날짜를 수정하면 `WRONG_DATE` Correction Log가 저장됩니다.

---

# 테스트 5: Canonical 재사용

1. 한 콘텐츠에서 엔티티 타입을 사용자 수정
2. 동일 엔티티가 들어간 다른 영상을 새로 분석
3. Spring 로그에:
```text
🧠 Canonical entity 자동 보정 적용
```
가 나오면 성공입니다.

---

# 후순위 개선

이번 버전에는 아직 넣지 않았습니다.
- 네이버/카카오 Local API 교차검증
- STT/OCR/Vision evidence provenance
- cross-modal confidence 재계산
- Golden Set 자동 평가
- Correction 데이터를 실제 few-shot prompt에 자동 삽입
- fine-tuning dataset export
- Interest Synthesis Agent 말투 개선

## Canonical DB 안전장치

사용자가 수정 화면을 저장했다고 해서 모든 AI 엔티티를 정답으로 간주하지 않습니다.

Canonical DB에는:
- 엔티티 이름을 실제로 수정한 경우
- 엔티티 타입을 실제로 수정한 경우
- 새 엔티티를 추가한 경우
- Action 직전 장소명을 실제로 수정한 경우

만 등록됩니다.

따라서 제목/요약만 수정했을 때 기존 AI 엔티티가 검증된 정답으로 오염되는 것을 방지합니다.


# Canonical DB 직접 확인

전체:
```bash
curl http://localhost:8080/api/v1/canonical-entities
```

이름 조회:
```bash
curl "http://localhost:8080/api/v1/canonical-entities/lookup?name=%EC%96%B4%EB%8B%88%EC%96%B8%20%EC%84%B1%EC%88%98"
```

사용자가 실제로 이름/타입을 수정한 엔티티만 들어가야 정상입니다.

# 카테고리 수정 제한

사용자가 직접 수정하더라도 상위 카테고리는 기존 Save:on taxonomy 안에서만 저장됩니다.

- 장소/여행
- 음식/레시피
- 제품/쇼핑
- 뷰티/패션
- 학습/커리어
- 건강/운동
- 생활정보
- 엔터테인먼트
- 기타

잘못 입력한 임의 상위 카테고리는 저장하지 않고 기존 값을 유지합니다.
