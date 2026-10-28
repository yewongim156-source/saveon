# Save:On 구조화·Semantic Search·사실 검증 구현 계획

## 목표

현재의 `제목/요약/카테고리/키워드/엔티티` 결과를 다음 세 계층으로 확장한다.

1. **카테고리별 구조화**: 안정적인 상위 분류와 동적 태그, 타입이 있는 엔티티, 검증 가능한 주장 생성
2. **개인 저장 콘텐츠 검색**: Gemini Embedding과 pgvector를 이용한 의미 검색
3. **근거 사실 검증**: 주장만 선별하여 Google Search Grounding으로 검증하고 출처를 보존

두 종류의 retrieval을 분리한다.

- `Library Retrieval`: 사용자가 저장한 콘텐츠를 pgvector에서 찾는다.
- `Evidence Retrieval`: 공개 웹에서 최신 근거를 찾고 영상의 주장과 비교한다.

## 범위와 원칙

- 기존 모바일 응답과 호환되도록 `title`, `summary`, `categories`, `keywords`, `entities`는 유지한다.
- 새로운 분석 결과는 `structured` 객체에 추가한다.
- 모든 생성 결과는 가능한 경우 영상 근거와 연결하고, 확인할 수 없는 값은 생성하지 않는다.
- 카테고리만으로 행동을 결정하지 않는다. 장소, 날짜, 팁 등 타입이 있는 데이터가 행동 카드의 입력이다.
- 사실 검증은 의견이 아니라 날짜, 가격, 장소, 성능, 건강 효과, 규정, 수치처럼 외부 검증이 가능한 주장에만 적용한다.
- 외부 API 장애 시 기존 규칙 기반 분석은 계속 동작해야 한다.

## 목표 응답 스키마

```json
{
  "title": "성수동 카페 5곳",
  "summary": "성수동에서 방문할 만한 카페를 소개한다.",
  "categories": ["장소/여행", "음식/레시피"],
  "keywords": ["성수", "카페", "데이트"],
  "entities": ["성수역"],
  "structured": {
    "primaryCategory": "장소/여행",
    "secondaryCategories": ["카페"],
    "tags": ["성수", "데이트"],
    "contentType": "PLACE_RECOMMENDATION",
    "entityDetails": [
      {
        "name": "성수역",
        "type": "PLACE",
        "confidence": 0.9
      }
    ],
    "claims": [
      {
        "text": "성수역에서 도보 5분 거리다",
        "type": "LOCATION",
        "verifiable": true,
        "searchQuery": "카페 이름 성수역 도보 거리"
      }
    ],
    "factChecks": []
  }
}
```

## 카테고리 구조

상위 카테고리는 검색과 통계를 위해 제한하고, 세부 관심사는 동적 태그로 둔다.

- 장소/여행
- 음식/레시피
- 제품/쇼핑
- 뷰티/패션
- 학습/커리어
- 건강/운동
- 생활정보
- 엔터테인먼트
- 기타

## Phase 1: 구조화 결과와 주장 추출

### AI

- Gemini Structured Output 스키마 확장
- 엔티티 타입: `PLACE`, `PRODUCT`, `BRAND`, `PERSON`, `SERVICE`, `EVENT`, `DATE`, `OTHER`
- 콘텐츠 타입: `PLACE_RECOMMENDATION`, `HOW_TO`, `PRODUCT_REVIEW`, `RECIPE`, `EVENT_INFO`, `EDUCATIONAL`, `NEWS_CLAIM`, `OTHER`
- 검증 가능한 주장 최대 3개 생성
- 기존 분석 fallback에도 빈 `structured` 객체 제공

### API/DB

- `contents.structured_analysis`에 전체 구조화 JSON 저장
- 기존 컬럼과 API 형식은 유지
- AI 응답에 새 필드가 추가되어도 역직렬화가 실패하지 않도록 DTO 확장

### 평가

- 카테고리 Macro F1
- 엔티티 타입 Precision/Recall/F1
- 검증 가능한 주장 Precision
- 요약의 입력 근거 일치 여부 수동 평가

## Phase 2: pgvector Semantic Search

### Embedding

- 모델: `gemini-embedding-2`
- 차원: 768
- 입력: 제목 + 요약 + 상위/하위 카테고리 + 태그 + 엔티티
- 모델명, 차원, 임베딩 생성 텍스트를 함께 저장한다.

### PostgreSQL

- 개발 DB 이미지를 `pgvector/pgvector:pg16`으로 변경
- `CREATE EXTENSION IF NOT EXISTS vector`
- `contents.embedding vector(768)`
- 데이터가 충분해지기 전에는 exact cosine search를 사용한다.
- 콘텐츠가 수천 건 이상 쌓이면 HNSW `vector_cosine_ops` 인덱스를 추가한다.

### API

- `POST /embed`: AI 서버의 임베딩 생성
- `GET /api/v1/contents/search/semantic?q=...&limit=20`
- 기존 키워드 검색은 유지한다.
- 다음 단계에서 keyword/semantic 결과를 Reciprocal Rank Fusion으로 합친다.

### 평가

- 질의-정답 콘텐츠 쌍을 구축
- Recall@5, MRR, nDCG@5
- 검색 API p95 latency

## Phase 3: 근거 사실 검증 RAG

### 처리 흐름

1. 구조화 단계에서 `verifiable=true`인 주장만 추출한다.
2. 주장별 검색어를 생성한다.
3. Gemini Google Search Grounding을 호출한다.
4. 근거와 주장을 비교해 판정한다.
5. 출처 URL, 제목, 설명, 신뢰도를 저장한다.

### 판정

- `SUPPORTED`
- `PARTIALLY_SUPPORTED`
- `CONFLICTING`
- `INSUFFICIENT_EVIDENCE`

### 비용·안전 정책

- 콘텐츠당 최대 3개 주장만 검증한다.
- 사실 검증은 환경변수로 켜고 끌 수 있게 한다.
- 검색 실패 시 `INSUFFICIENT_EVIDENCE`로 처리하며 분석 전체를 실패시키지 않는다.
- 건강, 투자, 법률 관련 결과는 확정적 조언으로 표시하지 않는다.

### 평가

- Evidence Recall@5
- 판정 정확도
- Citation precision
- 틀린 주장을 `SUPPORTED`로 판정한 비율

## 구현 순서

1. 구조화 Pydantic/Java DTO와 DB 저장
2. 임베딩 AI API
3. pgvector DB와 semantic search API
4. 주장 검증 서비스와 출처 저장
5. 모바일 상세 화면에 구조화 결과와 검증 출처 표시
6. hybrid search와 개인 콘텐츠 RAG 응답 생성

## 완료 기준

- Gemini 키가 없을 때 기존 분석이 정상 완료된다.
- 키가 있을 때 구조화 결과와 768차원 임베딩이 저장된다.
- 자연어 질의로 의미상 가까운 저장 콘텐츠가 검색된다.
- 검증 가능한 주장에 판정과 최소 1개의 출처가 연결된다.
- 검색 또는 검증 실패가 원본 콘텐츠 저장을 막지 않는다.
