# save:on — 비동기 URL 분석 + iOS Share Extension

## 이번 패치에서 바뀌는 것

1. URL 저장 API는 AI 분석이 끝날 때까지 기다리지 않습니다.
2. Spring이 Content를 `ANALYZING`으로 저장한 뒤 즉시 201 응답을 반환합니다.
3. `ContentAnalysisWorker`가 별도 스레드에서 FastAPI 분석을 실행합니다.
4. 성공하면 `COMPLETED`, 실패하면 `FAILED`로 DB를 갱신합니다.
5. 메인 앱은 `분석중` 콘텐츠가 있으면 4초마다 조용히 새로고침합니다.
6. iOS Share Extension에서 Instagram/YouTube URL을 서버에 직접 저장합니다.
7. Share Extension은 메인 앱을 열지 않고, 서버가 접수한 뒤 자동으로 닫힙니다.

## 주의

- 이번 1차 비동기화 대상은 URL 분석입니다.
- 갤러리 영상 직접 업로드는 기존 동기 방식 그대로입니다.
- `expo-share-extension`은 iOS Share Extension용입니다.
- 실제 iPhone에서 `localhost`는 Mac이 아닙니다.
  `.env`의 `EXPO_PUBLIC_API_BASE_URL`을 iPhone에서 접근 가능한 Spring 주소로 바꿔야 합니다.
