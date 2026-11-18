# Save:On 로컬 E2E 환경

모든 로컬 실행 파일과 데이터는 `미디어프로젝트/saveon` 안에 둔다.
대용량 런타임과 데이터베이스는 `.runtime/`, Python 패키지는 각
서비스의 `.venv/`에 있으며 Git에는 올리지 않는다.

## 현재 로컬 구성

- PostgreSQL 16.15 + pgvector 0.8.7: `localhost:5432`
- Spring API: `http://localhost:8080`
- AI API: `http://localhost:8000`
- Developer API: `http://localhost:8100`
- Mobile: React Native/Expo 프로젝트 (`mobile/`)

한국어 경로를 Windows용 PostgreSQL이 잘못 해석하는 문제를 피하기 위해
실행 중에만 저장소를 `S:`로 매핑한다. 데이터의 실제 위치는 바뀌지 않는다.

## Gemini 키 설정

`ai/.env`의 아래 값을 본인의 키로 채운다. 키는 Git에서 제외되며 채팅이나
커밋에 올리지 않는다.

```dotenv
GEMINI_API_KEY=your_key_here
```

키가 없으면 일반 URL 저장과 서비스 연결은 확인할 수 있지만 다음 기능은
작동하지 않는다.

- 영상 분석 결과의 구조화 및 카테고리 분류
- Google Search 기반 사실 검증과 `verifiedSummary`
- Gemini 임베딩 및 pgvector 의미 검색

## 실행

저장소 루트에서 다음 명령을 실행한다.

```powershell
.\scripts\Start-SaveOn.ps1
```

세 서비스와 DB 연결만 점검하려면:

```powershell
.\scripts\Test-SaveOnE2E.ps1
```

공개 YouTube 영상으로 전체 파이프라인을 점검하려면:

```powershell
.\scripts\Test-SaveOnE2E.ps1 -YouTubeUrl "https://www.youtube.com/shorts/..."
```

첫 영상 분석 시 Whisper, EasyOCR, CLIP 모델이 프로젝트의 로컬 캐시에
다운로드될 수 있어 평소보다 오래 걸린다.

## 종료

```powershell
.\scripts\Stop-SaveOn.ps1
```

로그는 `.runtime/logs/`에서 확인한다. AI 파이프라인 단계별 기록은
Developer API의 `/admin/overview`, `/admin/traces`,
`/admin/traces/{traceId}`에서 조회한다.
