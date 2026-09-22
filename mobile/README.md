# SaveOn - AI 스마트 콘텐츠 저장 앱 MVP

졸업작품용 1차 실행 가능한 Expo/React Native 프로토타입입니다.

## 현재 구현된 기능

- 홈 대시보드
- 콘텐츠 URL 저장
- Instagram / YouTube / Web URL 플랫폼 자동 판별
- 영상 파일 선택
- 보관함
- 카테고리 필터
- 콘텐츠 상세
- 로컬 키워드 검색
- 반복 등장 엔티티 표시
- AsyncStorage 기반 로컬 저장
- 향후 Spring Boot / FastAPI 연동용 API 클라이언트 구조

## 실행

```bash
npm install
npm start
```

iPhone에서 Expo Go를 사용하는 경우 터미널에 표시되는 QR 코드를 스캔합니다.

## API 서버 연결

`.env.example`을 `.env`로 복사한 뒤 API 주소를 설정합니다.

```env
EXPO_PUBLIC_API_BASE_URL=http://localhost:8080/api/v1
```

실기기에서 API를 연결할 때는 `localhost` 대신 Mac의 같은 Wi-Fi 내부 IP를 사용해야 합니다.

## 다음 개발 순서

1. Spring Boot `POST /contents` / `GET /contents` 연결
2. FastAPI 영상 분석 API 구축
3. STT + OCR + Vision + LLM JSON 구조화
4. PostgreSQL + pgvector 자연어 검색
5. Entity 테이블 및 콘텐츠 간 연결
6. iOS Share Extension / Android Share Intent
7. 저장 패턴 통계

## 주의

현재 URL 저장 시 AI 분석 결과는 데모용 mock 데이터입니다. `src/lib/api.ts`의 API 호출을 실제 백엔드 응답으로 교체하면 됩니다.

iOS에서 다른 앱의 공유 시트로부터 URL을 받는 기능은 Expo Go만으로 완성되지 않으며 custom development build와 native Share Extension 설정이 필요합니다.
