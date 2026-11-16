package com.saveon.api.comparison;

import com.saveon.api.comparison.agent.CollectionComparisonAgentClient;
import com.saveon.api.comparison.dto.CollectionComparisonRequest;
import com.saveon.api.comparison.dto.CollectionComparisonResponse;
import com.saveon.api.content.Content;
import com.saveon.api.content.ContentService;
import com.saveon.api.content.ContentSourceIdentity;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
public class CollectionComparisonService {

    private static final Set<String> COMPARABLE_ENTITY_TYPES =
            Set.of(
                    "PLACE",
                    "PRODUCT",
                    "BRAND",
                    "SERVICE"
            );

    private final ContentService contentService;
    private final CollectionComparisonAgentClient agentClient;
    private final JsonMapper jsonMapper;

    public CollectionComparisonService(
            ContentService contentService,
            CollectionComparisonAgentClient agentClient
    ) {
        this.contentService = contentService;
        this.agentClient = agentClient;
        this.jsonMapper = JsonMapper.builder().build();
    }

    public CollectionComparisonResponse compare(
            CollectionComparisonRequest request
    ) {
        if (request == null
                || request.contentIds() == null
                || request.contentIds().size() < 2) {
            throw new IllegalArgumentException(
                    "비교할 저장물을 2개 이상 선택해 주세요."
            );
        }

        List<Long> ids = request.contentIds()
                .stream()
                .distinct()
                .limit(8)
                .toList();

        Map<String, Content> uniqueVideos = new LinkedHashMap<>();
        for (Long id : ids) {
            Content content = contentService.findById(id);
            String sourceKey = ContentSourceIdentity.key(
                    content.getSourceUrl(), content.getId());
            uniqueVideos.putIfAbsent(sourceKey, content);
        }

        List<Content> contents = new ArrayList<>(uniqueVideos.values());
        if (contents.size() < 2) {
            return new CollectionComparisonResponse(
                    false,
                    "같은 영상을 중복 저장한 경우에는 서로 다른 영상으로 비교할 수 없어요.",
                    "",
                    request.collectionTitle() == null
                            ? "저장물 비교" : request.collectionTitle(),
                    "서로 다른 저장물을 2개 이상 선택해 주세요.",
                    List.of(), List.of(), List.of(), List.of(),
                    List.of(), List.of()
            );
        }

        String comparisonEntity =
                findRepeatedComparisonEntity(contents);

        List<Map<String, Object>> contexts =
                new ArrayList<>();

        for (Content content : contents) {
            Map<String, Object> context =
                    new LinkedHashMap<>();

            context.put("contentId", content.getId());
            context.put(
                    "title",
                    content.getTitle() != null
                            ? content.getTitle()
                            : ""
            );
            context.put(
                    "summary",
                    content.getSummary() != null
                            ? content.getSummary()
                            : ""
            );
            context.put(
                    "categories",
                    content.getCategories() != null
                            ? content.getCategories()
                            : List.of()
            );
            context.put(
                    "keywords",
                    content.getKeywords() != null
                            ? content.getKeywords()
                            : List.of()
            );
            context.put(
                    "entities",
                    content.getEntities() != null
                            ? content.getEntities()
                            : List.of()
            );
            context.put(
                    "structured",
                    parseStructured(
                            content.getStructuredAnalysis()
                    )
            );

            contexts.add(context);
        }

        Map<String, Object> body =
                new LinkedHashMap<>();

        body.put(
                "collectionTitle",
                request.collectionTitle() != null
                        ? request.collectionTitle()
                        : ""
        );
        body.put(
                "comparisonEntity",
                comparisonEntity
        );
        body.put("contexts", contexts);
        body.put("autoVerifyExternal", true);

        return agentClient.compare(body);
    }

    private String findRepeatedComparisonEntity(
            List<Content> contents
    ) {
        Map<String, EntityCount> counts =
                new HashMap<>();

        for (Content content : contents) {
            Set<String> seenInContent =
                    new LinkedHashSet<>();

            Map<String, Object> structured =
                    parseStructured(
                            content.getStructuredAnalysis()
                    );

            Object detailsRaw =
                    structured.get("entityDetails");

            if (detailsRaw instanceof List<?> details) {
                for (Object raw : details) {
                    if (!(raw instanceof Map<?, ?> item)) {
                        continue;
                    }

                    String name =
                            normalizeEntityName(
                                    item.get("name")
                            );

                    Object typeValue = item.get("type");
                    String type =
                            String.valueOf(
                                    typeValue != null
                                            ? typeValue
                                            : "OTHER"
                            ).toUpperCase(Locale.ROOT);

                    double confidence =
                            parseConfidence(
                                    item.get("confidence")
                            );

                    if (name.isBlank()
                            || !COMPARABLE_ENTITY_TYPES.contains(type)
                            || confidence < 0.45) {
                        continue;
                    }

                    String key =
                            name.toLowerCase(
                                    Locale.ROOT
                            );

                    if (!seenInContent.add(key)) {
                        continue;
                    }

                    counts.compute(
                            key,
                            (ignored, old) -> {
                                if (old == null) {
                                    return new EntityCount(
                                            name,
                                            type,
                                            1
                                    );
                                }

                                return new EntityCount(
                                        old.name(),
                                        old.type(),
                                        old.count() + 1
                                );
                            }
                    );
                }
            }

            // Top-level entities can contain a cleaner/canonical label than an
            // older structured payload, so always use them as supporting evidence.
            if (content.getEntities() != null) {
                for (String rawName : content.getEntities()) {
                    String name =
                            normalizeEntityName(rawName);

                    // A top-level entity can come from noisy OCR. Only treat it
                    // as a comparison target if it has independent support in
                    // the saved video's title, summary or keywords. Trusted
                    // structured entityDetails were already counted above.
                    if (name.isBlank()
                            || normalizeAnchorToken(name).isBlank()
                            || !hasTextEvidence(content, name)) {
                        continue;
                    }

                    String key =
                            name.toLowerCase(Locale.ROOT);

                    if (!seenInContent.add(key)) {
                        continue;
                    }

                    counts.compute(
                            key,
                            (ignored, old) -> {
                                if (old == null) {
                                    return new EntityCount(
                                            name,
                                            "UNKNOWN",
                                            1
                                    );
                                }

                                return new EntityCount(
                                        old.name(),
                                        old.type(),
                                        old.count() + 1
                                );
                            }
                    );
                }
            }
        }

        String direct = counts.values()
                .stream()
                .filter(item -> item.count() >= 2)
                .sorted(
                        Comparator
                                .comparingInt(
                                        EntityCount::count
                                )
                                .reversed()
                                .thenComparing(
                                        Comparator.comparingInt(
                                                (EntityCount item) -> item.name().length()
                                        ).reversed()
                                )
                )
                .map(EntityCount::name)
                .findFirst()
                .orElse("");

        if (!direct.isBlank()) {
            return direct;
        }

        // Older analyses may spell the same subject differently or may only
        // have captured it in title/summary/keywords. Recover a repeated
        // subject anchor from user-visible text instead of declaring the
        // collection non-comparable.
        return findRepeatedTextAnchor(contents);
    }

    private boolean hasTextEvidence(Content content, String entity) {
        String normalized = entity.toLowerCase(Locale.ROOT);
        List<String> evidence = new ArrayList<>();

        if (content.getTitle() != null) {
            evidence.add(content.getTitle());
        }
        if (content.getSummary() != null) {
            evidence.add(content.getSummary());
        }
        if (content.getKeywords() != null) {
            evidence.addAll(content.getKeywords());
        }

        for (String value : evidence) {
            if (value != null
                    && value.toLowerCase(Locale.ROOT).contains(normalized)) {
                return true;
            }
        }
        return false;
    }

    private String findRepeatedTextAnchor(
            List<Content> contents
    ) {
        Map<String, AnchorCount> counts =
                new HashMap<>();

        for (Content content : contents) {
            Set<String> seen =
                    new LinkedHashSet<>();

            List<String> sources =
                    new ArrayList<>();

            if (content.getTitle() != null) {
                sources.add(content.getTitle());
            }
            if (content.getSummary() != null) {
                sources.add(content.getSummary());
            }
            if (content.getKeywords() != null) {
                sources.addAll(content.getKeywords());
            }

            for (String source : sources) {
                if (source == null || source.isBlank()) {
                    continue;
                }

                for (String token : source.split(
                        "[^가-힣A-Za-z0-9]+"
                )) {
                    String cleaned =
                            normalizeAnchorToken(token);

                    if (cleaned.isBlank()
                            || !seen.add(cleaned)) {
                        continue;
                    }

                    counts.compute(
                            cleaned,
                            (ignored, old) -> {
                                if (old == null) {
                                    return new AnchorCount(
                                            token.trim(),
                                            1
                                    );
                                }
                                return new AnchorCount(
                                        old.label(),
                                        old.count() + 1
                                );
                            }
                    );
                }
            }
        }

        return counts.values().stream()
                .filter(value -> value.count() >= 2)
                .sorted(
                        Comparator
                                .comparingInt(
                                        AnchorCount::count
                                )
                                .reversed()
                                .thenComparing(
                                        Comparator.comparingInt(
                                                (AnchorCount value) ->
                                                        anchorSpecificity(value.label())
                                        ).reversed()
                                )
                )
                .map(AnchorCount::label)
                .findFirst()
                .orElse("");
    }

    private String normalizeAnchorToken(
            String raw
    ) {
        String value = raw == null
                ? ""
                : raw.trim().toLowerCase(Locale.ROOT);

        if (value.length() < 2
                || value.length() > 30) {
            return "";
        }

        Set<String> stopwords = Set.of(
                "영상",
                "리뷰",
                "추천",
                "신상",
                "사용",
                "테스트",
                "솔직",
                "new",
                "youtube",
                "shorts",
                "쿠션",
                "메이크업",
                "제품",
                "이번",
                "오늘",
                "관련"
        );

        if (stopwords.contains(value)) {
            return "";
        }

        return value;
    }

    private int anchorSpecificity(
            String label
    ) {
        if (label == null) {
            return 0;
        }

        int score = Math.min(label.length(), 12);
        if (label.matches(".*[A-Za-z].*")) {
            score += 1;
        }
        return score;
    }

    private String normalizeEntityName(
            Object value
    ) {
        if (value == null) {
            return "";
        }

        return String.valueOf(value)
                .replaceAll("\\s+", " ")
                .trim();
    }

    private double parseConfidence(
            Object value
    ) {
        if (value instanceof Number number) {
            return number.doubleValue();
        }

        try {
            return Double.parseDouble(
                    String.valueOf(value)
            );
        } catch (Exception ignored) {
            return 0.0;
        }
    }

    private Map<String, Object> parseStructured(
            String raw
    ) {
        if (raw == null || raw.isBlank()) {
            return Map.of();
        }

        try {
            JsonNode node = jsonMapper.readTree(raw);
            return jsonMapper.convertValue(
                    node,
                    Map.class
            );
        } catch (Exception ignored) {
            return Map.of();
        }
    }

    private record AnchorCount(
            String label,
            int count
    ) {
    }

    private record EntityCount(
            String name,
            String type,
            int count
    ) {
    }
}
