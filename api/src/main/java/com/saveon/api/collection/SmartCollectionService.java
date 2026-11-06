package com.saveon.api.collection;

import com.saveon.api.collection.agent.SmartCollectionAgentClient;
import com.saveon.api.collection.agent.SmartCollectionNameResponse;
import com.saveon.api.collection.dto.SmartCollectionItemResponse;
import com.saveon.api.collection.dto.SmartCollectionResponse;
import com.saveon.api.content.Content;
import com.saveon.api.content.ContentService;
import com.saveon.api.content.ContentStatus;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class SmartCollectionService {

    private static final int DEFAULT_LIMIT = 6;
    private static final int MAX_LIMIT = 10;
    private static final int MAX_SEEDS = 10;
    private static final int SEMANTIC_CANDIDATES = 12;
    private static final int MAX_ITEMS_PER_COLLECTION = 8;

    private static final Set<String> GENERIC_TERMS = Set.of(
            "기타",
            "영상",
            "콘텐츠",
            "정보",
            "추천",
            "리뷰",
            "일상",
            "브이로그",
            "shorts",
            "reels"
    );

    private static final Set<String> BROAD_COLLECTION_TERMS = Set.of(
            "맛집",
            "카페",
            "여행",
            "뷰티",
            "쇼핑",
            "패션",
            "공부",
            "기술",
            "운동",
            "생활",
            "생활정보",
            "엔터테인먼트",
            "음식",
            "레시피",
            "제품"
    );

    private final ContentService contentService;
    private final SmartCollectionAgentClient agentClient;
    private final JsonMapper jsonMapper;

    public SmartCollectionService(
            ContentService contentService,
            SmartCollectionAgentClient agentClient
    ) {
        this.contentService = contentService;
        this.agentClient = agentClient;
        this.jsonMapper = JsonMapper.builder().build();
    }

    public List<SmartCollectionResponse> findCollections(
            Integer requestedLimit
    ) {
        int limit =
                requestedLimit != null
                        ? requestedLimit
                        : DEFAULT_LIMIT;

        limit = Math.max(1, Math.min(limit, MAX_LIMIT));

        List<ContentProfile> profiles =
                contentService.findAll().stream()
                        .filter(content ->
                                content.getStatus()
                                        == ContentStatus.COMPLETED
                        )
                        .map(this::profile)
                        .toList();

        if (profiles.size() < 2) {
            return List.of();
        }

        List<String> seeds =
                selectSeeds(profiles);

        List<CollectionCandidate> candidates =
                new ArrayList<>();

        for (String seed : seeds) {
            try {
                List<Content> semanticallySimilar =
                        contentService.semanticSearch(
                                seed,
                                SEMANTIC_CANDIDATES
                        );

                Map<Long, ContentProfile> byId =
                        profiles.stream()
                                .collect(Collectors.toMap(
                                        value -> value.content().getId(),
                                        value -> value
                                ));

                List<ContentProfile> members =
                        semanticallySimilar.stream()
                                .map(content ->
                                        byId.get(content.getId())
                                )
                                .filter(value -> value != null)
                                .filter(value ->
                                        matchesStrongSeed(value, seed)
                                                || strongMetadataAffinity(
                                                        value,
                                                        seed
                                                ) >= 2
                                )
                                .limit(MAX_ITEMS_PER_COLLECTION)
                                .toList();

                if (members.size() >= 2) {
                    candidates.add(
                            buildCandidate(seed, members)
                    );
                }

            } catch (Exception semanticError) {
                // Semantic search can be unavailable while the AI server is down.
                // Use deterministic metadata grouping as fallback.
                List<ContentProfile> members =
                        profiles.stream()
                                .filter(value ->
                                        matchesStrongSeed(value, seed)
                                )
                                .limit(MAX_ITEMS_PER_COLLECTION)
                                .toList();

                if (members.size() >= 2) {
                    candidates.add(
                            buildCandidate(seed, members)
                    );
                }
            }
        }

        candidates.sort(
                Comparator
                        .comparingInt(
                                (CollectionCandidate value) ->
                                        value.members().size()
                        )
                        .reversed()
                        .thenComparingInt(
                                CollectionCandidate::specificity
                        )
                        .reversed()
        );

        List<CollectionCandidate> deduped =
                deduplicate(candidates);

        return deduped.stream()
                .limit(limit)
                .map(this::toResponse)
                .toList();
    }

    private List<String> selectSeeds(
            List<ContentProfile> profiles
    ) {
        Map<String, SeedScore> scores =
                new HashMap<>();

        for (ContentProfile profile : profiles) {
            Set<String> seenInContent =
                    new HashSet<>();

            for (String value : profile.entities()) {
                addSeed(scores, seenInContent, value, 8);
            }

            for (String value : profile.keywords()) {
                addSeed(scores, seenInContent, value, 5);
            }

            for (String value : profile.tags()) {
                addSeed(scores, seenInContent, value, 2);
            }
        }

        return scores.entrySet().stream()
                .filter(entry ->
                        entry.getValue().count() >= 2
                )
                .sorted(
                        Comparator
                                .<Map.Entry<String, SeedScore>>
                                        comparingInt(entry ->
                                                entry.getValue().score()
                                        )
                                .reversed()
                                .thenComparingInt(entry ->
                                        entry.getValue().count()
                                )
                                .reversed()
                )
                .map(Map.Entry::getKey)
                .filter(seed ->
                        !isGeneric(seed)
                )
                .limit(MAX_SEEDS)
                .toList();
    }

    private void addSeed(
            Map<String, SeedScore> scores,
            Set<String> seenInContent,
            String raw,
            int weight
    ) {
        String seed = clean(raw);

        if (seed.isBlank()
                || seed.length() < 2
                || seed.length() > 40
                || isGeneric(seed)
                || isBroadCollectionTerm(seed)) {
            return;
        }

        String normalized =
                seed.toLowerCase(Locale.ROOT);

        if (!seenInContent.add(normalized)) {
            return;
        }

        scores.compute(
                seed,
                (ignored, current) -> {
                    if (current == null) {
                        return new SeedScore(
                                1,
                                weight
                        );
                    }

                    return new SeedScore(
                            current.count() + 1,
                            current.score() + weight
                    );
                }
        );
    }

    private boolean matchesStrongSeed(
            ContentProfile profile,
            String seed
    ) {
        String normalized =
                clean(seed).toLowerCase(Locale.ROOT);

        return profile.strongTerms().stream()
                .map(value ->
                        clean(value).toLowerCase(Locale.ROOT)
                )
                .anyMatch(value ->
                        value.equals(normalized)
                                || (
                                normalized.length() >= 3
                                        && value.contains(normalized)
                        )
                                || (
                                value.length() >= 3
                                        && normalized.contains(value)
                        )
                );
    }

    private int strongMetadataAffinity(
            ContentProfile profile,
            String seed
    ) {
        String normalizedSeed =
                clean(seed).toLowerCase(Locale.ROOT);

        int score = 0;

        for (String value : profile.strongTerms()) {
            String normalized =
                    clean(value).toLowerCase(Locale.ROOT);

            if (normalized.equals(normalizedSeed)) {
                score += 4;
            } else if (
                    normalizedSeed.length() >= 3
                            && normalized.contains(normalizedSeed)
            ) {
                score += 2;
            } else if (
                    normalized.length() >= 3
                            && normalizedSeed.contains(normalized)
            ) {
                score += 2;
            }
        }

        return score;
    }

    private CollectionCandidate buildCandidate(
            String seed,
            List<ContentProfile> members
    ) {
        List<String> commonCategories =
                commonTerms(
                        members,
                        ContentProfile::categories,
                        4
                );

        List<String> commonKeywords =
                commonTerms(
                        members,
                        ContentProfile::keywords,
                        8
                );

        List<String> commonEntities =
                commonTerms(
                        members,
                        ContentProfile::entities,
                        8
                );

        if (!commonEntities.isEmpty()
                || !commonKeywords.isEmpty()) {
            commonCategories = List.of();
        }

        int specificity =
                commonEntities.size() * 4
                        + commonKeywords.size() * 2;

        return new CollectionCandidate(
                seed,
                members,
                commonCategories,
                commonKeywords,
                commonEntities,
                specificity
        );
    }

    private interface TermExtractor {
        List<String> get(ContentProfile profile);
    }

    private List<String> commonTerms(
            List<ContentProfile> members,
            TermExtractor extractor,
            int max
    ) {
        Map<String, Integer> counts =
                new LinkedHashMap<>();

        for (ContentProfile member : members) {
            Set<String> unique =
                    extractor.get(member).stream()
                            .map(this::clean)
                            .filter(value -> !value.isBlank())
                            .filter(value -> !isGeneric(value))
                            .collect(Collectors.toCollection(
                                    LinkedHashSet::new
                            ));

            for (String value : unique) {
                counts.merge(value, 1, Integer::sum);
            }
        }

        return counts.entrySet().stream()
                .filter(entry ->
                        entry.getValue() >= 2
                )
                .sorted(
                        Map.Entry
                                .<String, Integer>
                                        comparingByValue()
                                .reversed()
                )
                .map(Map.Entry::getKey)
                .limit(max)
                .toList();
    }

    private List<CollectionCandidate> deduplicate(
            List<CollectionCandidate> candidates
    ) {
        List<CollectionCandidate> result =
                new ArrayList<>();

        for (CollectionCandidate candidate : candidates) {
            Set<Long> candidateIds =
                    candidate.members().stream()
                            .map(value ->
                                    value.content().getId()
                            )
                            .collect(Collectors.toSet());

            boolean duplicate = false;

            for (CollectionCandidate accepted : result) {
                Set<Long> acceptedIds =
                        accepted.members().stream()
                                .map(value ->
                                        value.content().getId()
                                )
                                .collect(Collectors.toSet());

                Set<Long> intersection =
                        new HashSet<>(candidateIds);
                intersection.retainAll(acceptedIds);

                Set<Long> union =
                        new HashSet<>(candidateIds);
                union.addAll(acceptedIds);

                double jaccard =
                        union.isEmpty()
                                ? 0.0
                                : (double) intersection.size()
                                / union.size();

                if (jaccard >= 0.75) {
                    duplicate = true;
                    break;
                }
            }

            if (!duplicate) {
                result.add(candidate);
            }
        }

        return result;
    }

    private SmartCollectionResponse toResponse(
            CollectionCandidate candidate
    ) {
        String title =
                fallbackTitle(candidate);

        String description =
                fallbackDescription(candidate);

        String source = "RULE_BASED";

        try {
            SmartCollectionNameResponse generated =
                    agentClient.name(
                            candidate.seed(),
                            candidate.members().stream()
                                    .map(value ->
                                            safe(
                                                    value.content()
                                                            .getTitle()
                                            )
                                    )
                                    .toList(),
                            candidate.members().stream()
                                    .map(value ->
                                            safe(
                                                    value.content()
                                                            .getSummary()
                                            )
                                    )
                                    .toList(),
                            candidate.commonCategories(),
                            candidate.commonKeywords(),
                            candidate.commonEntities()
                    );

            if (generated != null) {
                if (generated.title() != null
                        && !generated.title().isBlank()) {
                    title = generated.title().trim();
                }

                if (generated.description() != null
                        && !generated.description().isBlank()) {
                    description =
                            generated.description().trim();
                }

                source = "AGENT";
            }
        } catch (Exception error) {
            // Rule-based title is intentionally sufficient as fallback.
        }

        List<SmartCollectionItemResponse> items =
                candidate.members().stream()
                        .map(value -> {
                            Content content =
                                    value.content();

                            return new SmartCollectionItemResponse(
                                    content.getId(),
                                    safe(content.getTitle()),
                                    safe(content.getSummary()),
                                    content.getPlatform() != null
                                            ? content.getPlatform().name()
                                            : "",
                                    safe(content.getSourceUrl())
                            );
                        })
                        .toList();

        return new SmartCollectionResponse(
                stableKey(candidate),
                candidate.seed(),
                title,
                description,
                items.size(),
                candidate.commonCategories(),
                candidate.commonKeywords(),
                candidate.commonEntities(),
                items,
                source
        );
    }

    private String fallbackTitle(
            CollectionCandidate candidate
    ) {
        String seed = candidate.seed();

        String topical =
                candidate.commonKeywords().stream()
                        .filter(value ->
                                !value.equalsIgnoreCase(seed)
                        )
                        .filter(value ->
                                value.length() <= 12
                        )
                        .findFirst()
                        .orElse("");

        if (!topical.isBlank()
                && seed.length() + topical.length() <= 18) {
            if (containsTopicWord(seed)
                    || containsTopicWord(topical)) {
                return clean(seed + " " + topical);
            }
        }

        return seed;
    }

    private String fallbackDescription(
            CollectionCandidate candidate
    ) {
        if (!candidate.commonKeywords().isEmpty()) {
            return candidate.seed()
                    + "와 관련해 "
                    + String.join(
                            ", ",
                            candidate.commonKeywords()
                                    .stream()
                                    .limit(3)
                                    .toList()
                    )
                    + " 내용이 반복해서 저장돼 있어요.";
        }

        return candidate.seed()
                + "와 비슷한 주제의 저장물 "
                + candidate.members().size()
                + "개를 자동으로 모았어요.";
    }

    private boolean containsTopicWord(
            String value
    ) {
        String text =
                value.toLowerCase(Locale.ROOT);

        return List.of(
                "카페",
                "맛집",
                "여행",
                "할인",
                "쇼핑",
                "메이크업",
                "패션",
                "운동",
                "공부",
                "레시피",
                "데이트",
                "숙소"
        ).stream().anyMatch(text::contains);
    }

    private ContentProfile profile(
            Content content
    ) {
        Map<String, Object> structured =
                parseStructured(
                        content.getStructuredAnalysis()
                );

        List<String> tags =
                stringList(structured.get("tags"));

        List<String> entityDetails =
                new ArrayList<>();

        Object details =
                structured.get("entityDetails");

        if (details instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    Object name = map.get("name");
                    Object typeValue = map.get("type");
                    Object confidenceValue = map.get("confidence");

                    String type =
                            typeValue != null
                                    ? String.valueOf(typeValue)
                                    .toUpperCase(Locale.ROOT)
                                    : "OTHER";

                    double confidence =
                            parseConfidence(confidenceValue);

                    if (name != null
                            && confidence >= 0.45
                            && Set.of(
                            "PLACE",
                            "PRODUCT",
                            "BRAND",
                            "SERVICE",
                            "PERSON",
                            "EVENT"
                    ).contains(type)) {
                        entityDetails.add(
                                clean(String.valueOf(name))
                        );
                    }
                }
            }
        }

        List<String> entities =
                new ArrayList<>(
                        content.getEntities() != null
                                ? content.getEntities()
                                : List.of()
                );

        for (String value : entityDetails) {
            if (!entities.contains(value)) {
                entities.add(value);
            }
        }

        return new ContentProfile(
                content,
                content.getCategories() != null
                        ? content.getCategories()
                        : List.of(),
                content.getKeywords() != null
                        ? content.getKeywords()
                        : List.of(),
                entities,
                tags
        );
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

    private boolean isBroadCollectionTerm(
            String value
    ) {
        String normalized =
                clean(value).toLowerCase(Locale.ROOT);

        return BROAD_COLLECTION_TERMS.contains(normalized);
    }

    private Map<String, Object> parseStructured(
            String raw
    ) {
        if (raw == null || raw.isBlank()) {
            return Map.of();
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> value =
                    jsonMapper.readValue(
                            raw,
                            Map.class
                    );

            return value;
        } catch (Exception ignored) {
            return Map.of();
        }
    }

    private List<String> stringList(
            Object value
    ) {
        if (!(value instanceof List<?> list)) {
            return List.of();
        }

        List<String> result =
                new ArrayList<>();

        for (Object item : list) {
            if (item != null) {
                String cleaned =
                        clean(String.valueOf(item));

                if (!cleaned.isBlank()
                        && !result.contains(cleaned)) {
                    result.add(cleaned);
                }
            }
        }

        return result;
    }

    private boolean isGeneric(
            String value
    ) {
        String normalized =
                clean(value)
                        .toLowerCase(Locale.ROOT);

        return GENERIC_TERMS.contains(normalized);
    }

    private String clean(
            String value
    ) {
        if (value == null) {
            return "";
        }

        return value
                .replaceAll("[#]+", "")
                .replaceAll("\\s+", " ")
                .trim();
    }

    private String stableKey(
            CollectionCandidate candidate
    ) {
        try {
            MessageDigest digest =
                    MessageDigest.getInstance("SHA-256");

            String raw =
                    candidate.seed()
                            + ":"
                            + candidate.members().stream()
                            .map(value ->
                                    String.valueOf(
                                            value.content().getId()
                                    )
                            )
                            .sorted()
                            .collect(Collectors.joining(","));

            byte[] hash =
                    digest.digest(
                            raw.getBytes(
                                    StandardCharsets.UTF_8
                            )
                    );

            StringBuilder builder =
                    new StringBuilder();

            for (int index = 0;
                 index < Math.min(8, hash.length);
                 index++) {
                builder.append(
                        String.format(
                                "%02x",
                                hash[index]
                        )
                );
            }

            return builder.toString();

        } catch (Exception ignored) {
            return String.valueOf(
                    Math.abs(
                            candidate.seed().hashCode()
                    )
            );
        }
    }

    private String safe(
            String value
    ) {
        return value != null ? value : "";
    }

    private record SeedScore(
            int count,
            int score
    ) {
    }

    private record ContentProfile(
            Content content,
            List<String> categories,
            List<String> keywords,
            List<String> entities,
            List<String> tags
    ) {
        List<String> strongTerms() {
            List<String> result =
                    new ArrayList<>();

            result.addAll(entities);
            result.addAll(keywords);
            result.addAll(tags);

            return result;
        }
    }

    private record CollectionCandidate(
            String seed,
            List<ContentProfile> members,
            List<String> commonCategories,
            List<String> commonKeywords,
            List<String> commonEntities,
            int specificity
    ) {
    }
}
