# Save:on Analysis Stability v1

이 패치는 비교 v2 / 리마인더 / 모바일 UI를 건드리지 않습니다.
분석 안정화에 필요한 파일만 덮어씁니다.

## 수정 내용

### 1. YouTube 저장 실패 완화
- 기본 최대 길이: 10분 -> 20분
- `YOUTUBE_MAX_DURATION_SECONDS`로 조절 가능
- 다운로드 직후 실제 파일 존재 + 최소 크기 검증
- 영상/오디오 파일 크기 로그 추가
- 빈 오디오면 영상 파일로 STT 재시도

### 2. Gemini 429 폭주 방지
- 기본 모델: `gemini-3.5-flash-lite`
- 429는 자동 재시도하지 않음
- 500/502/503/504만 짧게 재시도
- timeout 30초
- 기존 품질 보호 fallback 유지

### 3. /embed 요청 폭주 완화
- 동일 텍스트 임베딩을 메모리에서 10분 캐시
- 최대 256개 LRU
- 임베딩 API 실패 직후 8초 cooldown
- 동일 Smart Collection/검색 polling이 같은 임베딩을 반복 호출하는 상황 감소

환경변수:
```env
EMBEDDING_CACHE_TTL_SECONDS=600
EMBEDDING_CACHE_MAX_ITEMS=256
EMBEDDING_FAILURE_COOLDOWN_SECONDS=8
```

### 4. fallback 품질 보호
Gemini가 429여도 기존 Quality v1 규칙을 유지합니다.
- OCR 조각을 entity로 저장하지 않음
- `Video by ...` 같은 generic title 보정
- description/caption을 fallback에서 적극 사용
- 쿠션/파운데이션/블러셔/뷰티 등의 카테고리 신호 강화
- low-confidence entity 제거

### 5. 직접 업로드 빈 바이트 방지
Spring `AiClient`가 0 byte 파일을 FastAPI로 보내기 전에 차단합니다.
원래 파일명도 X-Filename에 전달합니다.

## 적용

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_analysis_stability_v1.zip -d ~/Downloads/saveon
```

## 재시작

8000:
```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn main:app --reload --port 8000
```

Spring:
```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

8001/8002/8003과 Expo는 이번 패치 때문에 재시작할 필요 없습니다.

## 테스트

문제였던 YouTube URL을 다시 저장합니다.

AI 로그에서 다음이 보이면 다운로드 계층 정상:
```text
[YOUTUBE] metadata ok: ...
[YOUTUBE] stream ready: ... / N bytes
[VIDEO] 분석 시작: ...
```

Gemini 무료 quota가 차면:
```text
[LLM] Gemini 후처리 실패 - 품질 보호 fallback 사용: 429 ...
```
가 나올 수 있지만 콘텐츠 분석 자체는 fallback으로 완료되어야 합니다.

동일 검색/컬렉션 요청에서는:
```text
[EMBED] cache hit
```
가 보이면 캐시가 작동 중입니다.
