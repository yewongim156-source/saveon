# save:on 관심 정보 묶음 v1

## 목적

구조화 기반 콘텐츠 연결 v1의 다음 단계입니다.

기존:

```text
올리브영
→ 관련 콘텐츠 2개
```

이번 버전:

```text
올리브영 · 브랜드
→ 관련 콘텐츠 2개 통합
→ 주요 카테고리
→ 공통 관심/태그
→ 공통 키워드
→ 함께 반복된 브랜드·장소·상품
→ 저장된 콘텐츠별 핵심 요약
→ 원본 관련 콘텐츠 목록
```

새로운 AI 호출은 추가하지 않습니다. 이미 저장된 분석/구조화 결과를 재사용하므로
팀원의 AI 구조화·Semantic Search·사실 검증 영역과 분리되어 있습니다.

## 통합 기준

연결 대상은 기존 v1과 동일합니다.

- 콘텐츠 상태: `COMPLETED`
- 구조화 엔티티 타입: `PLACE`, `PRODUCT`, `BRAND`, `PERSON`, `SERVICE`
- confidence >= 0.65
- 같은 `type + entity name`이 2개 이상 콘텐츠에 등장

관심 정보 묶음은 연결된 콘텐츠에서 다음 정보를 집계합니다.

- `categories`: 많이 등장한 카테고리 최대 3개
- `commonKeywords`: 여러 콘텐츠에서 공통으로 등장한 키워드 최대 6개
- `commonTags`: structuredAnalysis.tags 공통 항목 최대 6개
- `relatedEntities`: 기준 엔티티 이외에 2개 이상 콘텐츠에서 함께 반복된 엔티티 최대 8개
- `highlights`: 연결된 콘텐츠 제목/요약 최대 5개
- `overview`: 위 결과를 이용해 서버에서 생성한 짧은 통합 설명

## 추가 API

```text
GET /api/v1/content-connections/bundle?type=BRAND&entity=올리브영
```

URL 인코딩 예시:

```bash
curl "http://localhost:8080/api/v1/content-connections/bundle?type=BRAND&entity=%EC%98%AC%EB%A6%AC%EB%B8%8C%EC%98%81"
```

## 적용

현재 `test/structured-connections` 브랜치에서 기존 연결 v1 테스트가 성공한 상태라면:

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_content_bundle_v1.zip -d .
```

네이티브 설정은 변경하지 않으므로 `expo prebuild --clean`은 필요 없습니다.

Spring 재시작:

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

모바일 Metro가 필요하면:

```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

## 현재 올리브영 테스트 데이터에서 기대되는 결과

현재 저장한 id 12, 13 기준으로 대략 다음처럼 나오는 것이 정상입니다.

- 루트: `올리브영 / BRAND / 2개`
- 주요 카테고리: `제품/쇼핑`, `뷰티/패션`
- 공통 태그 후보: `올영세일`, `블프`, `쇼핑팁`, `올리브영추천`
- 공통 키워드 후보: `올영세일`, `블랙프라이데이`, `올영블프`, `뷰티MD`, `쇼핑꿀팁`
- 함께 반복된 브랜드: `웰라쥬`, `토리든`, `메노킨`
- 저장된 정보 요약: 연결된 두 콘텐츠의 title/summary

모바일에서는 홈의 `올리브영` 카드를 누르면 화면 상단에 `관심 정보 묶음`이 먼저 보이고,
그 아래에 기존 `관련 콘텐츠` 2개가 표시됩니다.
