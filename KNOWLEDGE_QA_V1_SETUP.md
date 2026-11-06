# save:on Saved Knowledge Q&A v1

사용자의 저장물만 근거로 질문에 답하는 Q&A 기능입니다.

## 사용자 흐름

검색 화면:
`검색 | 질문`

질문 예:
- 내가 저장한 성수 카페 중 빵이 유명한 곳은?
- 올리브영 관련해서 저장한 내용 정리해줘
- 여행 저장물에서 장소만 알려줘

처리:
1. Spring semantic search로 관련 저장물 Top-K 검색
2. COMPLETED 저장물만 Q&A context로 사용
3. Q&A Agent(8003)가 제공된 저장물만 보고 답변
4. 답변에 직접 사용한 contentId만 source로 반환
5. 앱에서 출처 저장물 카드를 누르면 상세 화면으로 이동

외부 웹 지식은 사용하지 않습니다.
근거가 부족하면 추측하지 않고
`저장한 콘텐츠만으로는 확인하기 어려워요.`라고 답합니다.

## 적용

현재 Quality/Learning v1 + User UX v2가 적용된 프로젝트 기준입니다.

```bash
cd ~/Downloads/saveon
unzip -o ~/Downloads/saveon_knowledge_qa_v1.zip -d ~/Downloads/saveon
```

## Q&A Agent 실행

새 터미널:

```bash
cd ~/Downloads/saveon/ai
source .venv/bin/activate
python -m uvicorn qna_agent:app --reload --port 8003
```

확인:

```bash
curl http://localhost:8003/health
```

예상:
```json
{
  "status":"ok",
  "service":"saveon-knowledge-qa-agent",
  "version":"1.0.0",
  "grounding":"USER_SAVED_CONTENT_ONLY"
}
```

## Spring 재시작

```bash
cd ~/Downloads/saveon/api
./gradlew bootRun
```

새 설정을 application.properties에 추가할 필요는 없습니다.
기본값으로 `http://localhost:8003`을 사용합니다.

원하면:
```properties
saveon.qna-agent.base-url=http://localhost:8003
```

## 모바일

native dependency가 추가되지 않았으므로 prebuild 필요 없습니다.

```bash
cd ~/Downloads/saveon/mobile
npx expo start --dev-client -c
```

## API 테스트

```bash
curl -X POST http://localhost:8080/api/v1/knowledge/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question":"내가 저장한 성수 카페 중 빵이 유명한 곳은?",
    "limit":5
  }'
```

응답 예:
```json
{
  "answer":"저장한 콘텐츠에서는 ...",
  "grounded":true,
  "sources":[
    {
      "contentId":14,
      "title":"성수동 핫플 카페 어니언...",
      "summary":"...",
      "platform":"YOUTUBE",
      "sourceUrl":"..."
    }
  ]
}
```

## 중요한 동작

- Q&A Agent가 죽어도 Spring은 500을 내지 않고 관련 저장물 3개를 fallback으로 반환합니다.
- semantic search가 동작하려면 8000 AI 서버와 embedding이 정상이어야 합니다.
- 기존 저장물에 embedding이 없는 경우 semantic search 결과가 적거나 없을 수 있습니다.
- Fact Verification/Verified Summary가 나중에 통합되면 Q&A는 `verifiedFacts`, `verificationStatus`, `corrections`, `unverifiedNotes`를 우선 참고하도록 이미 설계했습니다.

## 테스트 순서

1. 8000 / 8001 / 8002 / 8003 / 8080 실행
2. 앱 → 검색 → 질문
3. 예시 질문 탭
4. 답변 생성 확인
5. `답변에 참고한 저장물` 확인
6. source card → 해당 콘텐츠 상세 이동 확인
7. 저장물에 없는 질문을 해보고 추측하지 않는지 확인
