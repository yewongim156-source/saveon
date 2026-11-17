package com.saveon.api.knowledge;

import com.saveon.api.content.Content;
import com.saveon.api.content.ContentStatus;
import com.saveon.api.content.ContentService;
import com.saveon.api.knowledge.agent.KnowledgeAgentClient;
import com.saveon.api.knowledge.agent.KnowledgeAgentResponse;
import com.saveon.api.knowledge.dto.KnowledgeAskResponse;
import com.saveon.api.knowledge.dto.KnowledgeSourceResponse;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class KnowledgeService {

    private static final int DEFAULT_LIMIT = 5;
    private static final int MAX_LIMIT = 8;

    private final ContentService contentService;
    private final KnowledgeAgentClient knowledgeAgentClient;
    private final JsonMapper jsonMapper;

    public KnowledgeService(
            ContentService contentService,
            KnowledgeAgentClient knowledgeAgentClient
    ) {
        this.contentService = contentService;
        this.knowledgeAgentClient = knowledgeAgentClient;
        this.jsonMapper = JsonMapper.builder().build();
    }

    public KnowledgeAskResponse ask(
            String rawQuestion,
            Integer requestedLimit
    ) {
        String question =
                rawQuestion == null
                        ? ""
                        : rawQuestion.trim();

        if (question.isBlank()) {
            throw new IllegalArgumentException(
                    "질문을 입력해 주세요."
            );
        }

        int limit =
                requestedLimit != null
                        ? requestedLimit
                        : DEFAULT_LIMIT;

        limit = Math.max(
                1,
                Math.min(limit, MAX_LIMIT)
        );

        List<Content> retrieved =
                contentService.semanticSearch(
                        question,
                        limit
                );

        List<Content> contexts =
                retrieved.stream()
                        .filter(content ->
                                content.getStatus()
                                        == ContentStatus.COMPLETED
                        )
                        .limit(limit)
                        .toList();

        if (contexts.isEmpty()) {
            return new KnowledgeAskResponse(
                    "내 저장물에서 이 질문과 관련된 내용을 아직 찾지 못했어요.",
                    false,
                    List.of()
            );
        }

        List<Map<String, Object>> agentContexts =
                contexts.stream()
                        .map(this::buildAgentContext)
                        .toList();

        try {
            KnowledgeAgentResponse agent =
                    knowledgeAgentClient.ask(
                            question,
                            agentContexts
                    );

            Set<Long> citedIds =
                    new HashSet<>(
                            agent != null
                                    && agent.citedContentIds() != null
                                    ? agent.citedContentIds()
                                    : List.of()
                    );

            List<KnowledgeSourceResponse> citedSources =
                    contexts.stream()
                            .filter(content ->
                                    citedIds.contains(content.getId())
                            )
                            .map(this::toSource)
                            .toList();

            String answer =
                    agent != null
                            && agent.answer() != null
                            && !agent.answer().isBlank()
                            ? agent.answer().trim()
                            : "저장한 콘텐츠만으로는 확인하기 어려워요.";

            return new KnowledgeAskResponse(
                    answer,
                    !citedSources.isEmpty(),
                    citedSources
            );

        } catch (Exception error) {
            System.err.println(
                    "⚠️ 저장물 Q&A Agent 실패 - 검색 결과만 반환: "
                            + error.getMessage()
            );

            List<KnowledgeSourceResponse> fallbackSources =
                    contexts.stream()
                            .limit(3)
                            .map(this::toSource)
                            .toList();

            return new KnowledgeAskResponse(
                    "관련 저장물은 찾았지만 답변을 정리하지 못했어요. 아래 저장물을 직접 확인해보세요.",
                    false,
                    fallbackSources
            );
        }
    }

    private Map<String, Object> buildAgentContext(
            Content content
    ) {
        Map<String, Object> result =
                new LinkedHashMap<>();

        result.put("contentId", content.getId());
        result.put("title", safe(content.getTitle()));
        result.put("summary", safe(content.getSummary()));
        result.put("categories", content.getCategories());
        result.put("entities", content.getEntities());
        result.put(
                "structured",
                parseStructured(
                        content.getStructuredAnalysis()
                )
        );

        return result;
    }

    private Map<String, Object> parseStructured(
            String raw
    ) {
        if (raw == null || raw.isBlank()) {
            return Map.of();
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> parsed =
                    jsonMapper.readValue(
                            raw,
                            Map.class
                    );

            Map<String, Object> compact =
                    new LinkedHashMap<>();

            copyIfPresent(parsed, compact, "primaryCategory");
            copyIfPresent(parsed, compact, "contentType");
            copyIfPresent(parsed, compact, "tags");
            copyIfPresent(parsed, compact, "entityDetails");
            copyIfPresent(parsed, compact, "claims");
            copyIfPresent(parsed, compact, "verificationStatus");
            copyIfPresent(parsed, compact, "verifiedFacts");
            copyIfPresent(parsed, compact, "corrections");
            copyIfPresent(parsed, compact, "unverifiedNotes");

            return compact;

        } catch (Exception error) {
            return Map.of();
        }
    }

    private void copyIfPresent(
            Map<String, Object> source,
            Map<String, Object> target,
            String key
    ) {
        Object value = source.get(key);

        if (value != null) {
            target.put(key, value);
        }
    }

    private KnowledgeSourceResponse toSource(
            Content content
    ) {
        return new KnowledgeSourceResponse(
                content.getId(),
                safe(content.getTitle()),
                safe(content.getSummary()),
                content.getPlatform() != null
                        ? content.getPlatform().name()
                        : "",
                safe(content.getSourceUrl())
        );
    }

    private String safe(String value) {
        return value != null ? value : "";
    }
}
