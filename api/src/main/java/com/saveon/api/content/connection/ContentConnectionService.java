package com.saveon.api.content.connection;

import com.saveon.api.content.Content;
import com.saveon.api.content.ContentRepository;
import com.saveon.api.content.ContentStatus;
import com.saveon.api.content.connection.dto.ContentBundleResponse;
import com.saveon.api.content.connection.dto.ContentConnectionResponse;
import com.saveon.api.content.connection.dto.ContentHighlightResponse;
import com.saveon.api.content.connection.dto.RelatedEntityResponse;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
public class ContentConnectionService {

    private static final double MIN_CONFIDENCE = 0.65;
    private static final int DEFAULT_LIMIT = 8;
    private static final int MAX_LIMIT = 30;

    private static final Set<String> CONNECTABLE_TYPES =
            Set.of(
                    "PLACE",
                    "PRODUCT",
                    "BRAND",
                    "PERSON",
                    "SERVICE"
            );

    private final ContentRepository contentRepository;
    private final JsonMapper jsonMapper;

    public ContentConnectionService(
            ContentRepository contentRepository
    ) {
        this.contentRepository =
                contentRepository;

        this.jsonMapper =
                JsonMapper.builder()
                        .build();
    }


    public List<ContentConnectionResponse> findConnections(
            String requestedType,
            Integer requestedLimit
    ) {
        String typeFilter =
                normalizeType(requestedType);

        int limit =
                requestedLimit == null
                        ? DEFAULT_LIMIT
                        : Math.max(
                                1,
                                Math.min(
                                        requestedLimit,
                                        MAX_LIMIT
                                )
                        );

        Map<String, ConnectionAccumulator> groups =
                new HashMap<>();

        for (Content content : contentRepository.findAll()) {
            if (content.getStatus()
                    != ContentStatus.COMPLETED) {
                continue;
            }

            Set<String> seenInContent =
                    new HashSet<>();

            for (StructuredEntity entity :
                    extractStructuredData(content)
                            .entities()) {

                if (!CONNECTABLE_TYPES.contains(
                        entity.type()
                )) {
                    continue;
                }

                if (entity.confidence()
                        < MIN_CONFIDENCE) {
                    continue;
                }

                if (typeFilter != null
                        && !typeFilter.equals(
                        entity.type()
                )) {
                    continue;
                }

                String normalizedName =
                        normalizeName(entity.name());

                if (normalizedName.isBlank()) {
                    continue;
                }

                String key =
                        entity.type()
                                + "|"
                                + normalizedName;

                // 같은 콘텐츠 안에서 같은 엔티티가
                // 여러 번 추출돼도 1회만 카운트한다.
                if (!seenInContent.add(key)) {
                    continue;
                }

                ConnectionAccumulator group =
                        groups.computeIfAbsent(
                                key,
                                ignored ->
                                        new ConnectionAccumulator(
                                                entity.name(),
                                                entity.type()
                                        )
                        );

                group.add(
                        content.getId(),
                        entity.confidence()
                );
            }
        }

        return groups.values()
                .stream()
                .filter(
                        group ->
                                group.count() >= 2
                )
                .sorted(
                        Comparator
                                .comparingLong(
                                        ConnectionAccumulator::count
                                )
                                .reversed()
                                .thenComparing(
                                        Comparator.comparingDouble(
                                                ConnectionAccumulator::confidence
                                        ).reversed()
                                )
                                .thenComparing(
                                        ConnectionAccumulator::entity
                                )
                )
                .limit(limit)
                .map(
                        group ->
                                new ContentConnectionResponse(
                                        group.entity(),
                                        group.type(),
                                        group.count(),
                                        roundConfidence(
                                                group.confidence()
                                        )
                                )
                )
                .toList();
    }


    public List<Content> findConnectedContents(
            String requestedType,
            String requestedEntity
    ) {
        String type =
                normalizeType(requestedType);

        if (type == null
                || !CONNECTABLE_TYPES.contains(type)) {
            return List.of();
        }

        String entity =
                normalizeName(requestedEntity);

        if (entity.isBlank()) {
            return List.of();
        }

        List<Content> matches =
                new ArrayList<>();

        for (Content content : contentRepository.findAll()) {
            if (content.getStatus()
                    != ContentStatus.COMPLETED) {
                continue;
            }

            boolean matched =
                    extractStructuredData(content)
                            .entities()
                            .stream()
                            .anyMatch(
                                    item ->
                                            type.equals(
                                                    item.type()
                                            )
                                                    && item.confidence()
                                                    >= MIN_CONFIDENCE
                                                    && entity.equals(
                                                    normalizeName(
                                                            item.name()
                                                    )
                                            )
                            );

            if (matched) {
                matches.add(content);
            }
        }

        matches.sort(
                Comparator.comparing(
                                Content::getCreatedAt,
                                Comparator.nullsLast(
                                        Comparator.naturalOrder()
                                )
                        )
                        .reversed()
        );

        return matches;
    }


    public ContentBundleResponse buildBundle(
            String requestedType,
            String requestedEntity
    ) {
        String type =
                normalizeType(requestedType);

        String entityName =
                requestedEntity == null
                        ? ""
                        : requestedEntity.trim();

        List<Content> contents =
                findConnectedContents(
                        requestedType,
                        requestedEntity
                );

        Map<String, Integer> categoryCounts =
                new HashMap<>();

        Map<String, Integer> keywordCounts =
                new HashMap<>();

        Map<String, Integer> tagCounts =
                new HashMap<>();

        Map<String, RelatedEntityAccumulator>
                relatedEntityGroups =
                new HashMap<>();

        List<ContentHighlightResponse> highlights =
                new ArrayList<>();

        String normalizedRoot =
                normalizeName(entityName);

        for (Content content : contents) {
            addUniqueValues(
                    categoryCounts,
                    content.getCategories(),
                    null
            );

            addUniqueValues(
                    keywordCounts,
                    content.getKeywords(),
                    normalizedRoot
            );

            StructuredData structured =
                    extractStructuredData(content);

            addUniqueValues(
                    tagCounts,
                    structured.tags(),
                    normalizedRoot
            );

            Set<String> seenRelated =
                    new HashSet<>();

            for (StructuredEntity related :
                    structured.entities()) {

                if (!CONNECTABLE_TYPES.contains(
                        related.type()
                )) {
                    continue;
                }

                if (related.confidence()
                        < MIN_CONFIDENCE) {
                    continue;
                }

                String normalized =
                        normalizeName(
                                related.name()
                        );

                if (normalized.isBlank()) {
                    continue;
                }

                if (type != null
                        && type.equals(
                        related.type()
                )
                        && normalizedRoot.equals(
                        normalized
                )) {
                    continue;
                }

                String key =
                        related.type()
                                + "|"
                                + normalized;

                if (!seenRelated.add(key)) {
                    continue;
                }

                RelatedEntityAccumulator group =
                        relatedEntityGroups
                                .computeIfAbsent(
                                        key,
                                        ignored ->
                                                new RelatedEntityAccumulator(
                                                        related.name(),
                                                        related.type()
                                                )
                                );

                group.add(
                        content.getId()
                );
            }

            if (highlights.size() < 5) {
                highlights.add(
                        new ContentHighlightResponse(
                                content.getId(),
                                safeTitle(
                                        content.getTitle()
                                ),
                                safeSummary(
                                        content.getSummary()
                                )
                        )
                );
            }
        }

        List<String> categories =
                topValues(
                        categoryCounts,
                        3,
                        1
                );

        List<String> commonKeywords =
                topValues(
                        keywordCounts,
                        6,
                        2
                );

        if (commonKeywords.isEmpty()) {
            commonKeywords =
                    topValues(
                            keywordCounts,
                            6,
                            1
                    );
        }

        List<String> commonTags =
                topValues(
                        tagCounts,
                        6,
                        2
                );

        if (commonTags.isEmpty()) {
            commonTags =
                    topValues(
                            tagCounts,
                            6,
                            1
                    );
        }

        List<RelatedEntityResponse> relatedEntities =
                relatedEntityGroups
                        .values()
                        .stream()
                        .filter(
                                group ->
                                        group.count() >= 2
                        )
                        .sorted(
                                Comparator
                                        .comparingLong(
                                                RelatedEntityAccumulator::count
                                        )
                                        .reversed()
                                        .thenComparing(
                                                RelatedEntityAccumulator::entity
                                        )
                        )
                        .limit(8)
                        .map(
                                group ->
                                        new RelatedEntityResponse(
                                                group.entity(),
                                                group.type(),
                                                group.count()
                                        )
                        )
                        .toList();

        String overview =
                buildOverview(
                        entityName,
                        type,
                        contents.size(),
                        commonKeywords,
                        commonTags,
                        relatedEntities
                );

        return new ContentBundleResponse(
                entityName,
                type != null ? type : "OTHER",
                contents.size(),
                overview,
                categories,
                commonKeywords,
                commonTags,
                relatedEntities,
                highlights
        );
    }


    private String buildOverview(
            String entity,
            String type,
            int count,
            List<String> keywords,
            List<String> tags,
            List<RelatedEntityResponse> related
    ) {
        if (count == 0) {
            return entity
                    + " 관련 저장 콘텐츠를 찾지 못했어요.";
        }

        StringBuilder builder =
                new StringBuilder();

        builder.append(entity)
                .append(" 관련 ")
                .append(typeLabel(type))
                .append(" 콘텐츠 ")
                .append(count)
                .append("개를 하나의 관심 정보로 묶었어요.");

        List<String> interests =
                !tags.isEmpty()
                        ? tags
                        : keywords;

        if (!interests.isEmpty()) {
            builder.append(" 주요 관심은 ")
                    .append(
                            String.join(
                                    ", ",
                                    interests
                                            .stream()
                                            .limit(3)
                                            .toList()
                            )
                    )
                    .append("예요.");
        }

        if (!related.isEmpty()) {
            builder.append(" 함께 반복된 정보는 ")
                    .append(
                            String.join(
                                    ", ",
                                    related
                                            .stream()
                                            .limit(3)
                                            .map(
                                                    RelatedEntityResponse::entity
                                            )
                                            .toList()
                            )
                    )
                    .append(" 등이 있어요.");
        }

        return builder.toString();
    }


    private String typeLabel(
            String type
    ) {
        if (type == null) {
            return "관련";
        }

        return switch (type) {
            case "PLACE" -> "장소";
            case "PRODUCT" -> "상품";
            case "BRAND" -> "브랜드";
            case "PERSON" -> "인물";
            case "SERVICE" -> "서비스";
            default -> "관련";
        };
    }


    private void addUniqueValues(
            Map<String, Integer> counts,
            List<String> values,
            String excludedNormalized
    ) {
        if (values == null) {
            return;
        }

        Set<String> seen =
                new HashSet<>();

        for (String value : values) {
            if (value == null) {
                continue;
            }

            String trimmed =
                    value.trim();

            String normalized =
                    normalizeName(trimmed);

            if (trimmed.isBlank()
                    || normalized.isBlank()) {
                continue;
            }

            if (excludedNormalized != null
                    && excludedNormalized.equals(
                    normalized
            )) {
                continue;
            }

            if (!seen.add(normalized)) {
                continue;
            }

            counts.merge(
                    trimmed,
                    1,
                    Integer::sum
            );
        }
    }


    private List<String> topValues(
            Map<String, Integer> counts,
            int limit,
            int minimumCount
    ) {
        return counts.entrySet()
                .stream()
                .filter(
                        entry ->
                                entry.getValue()
                                        >= minimumCount
                )
                .sorted(
                        Map.Entry
                                .<String, Integer>
                                comparingByValue()
                                .reversed()
                                .thenComparing(
                                        Map.Entry.comparingByKey()
                                )
                )
                .limit(limit)
                .map(
                        Map.Entry::getKey
                )
                .toList();
    }


    private StructuredData extractStructuredData(
            Content content
    ) {
        String raw =
                content.getStructuredAnalysis();

        if (raw == null
                || raw.isBlank()) {
            return new StructuredData(
                    List.of(),
                    List.of()
            );
        }

        try {
            Map<?, ?> structured =
                    jsonMapper.readValue(
                            raw,
                            Map.class
                    );

            List<StructuredEntity> entities =
                    extractEntityDetails(
                            structured.get(
                                    "entityDetails"
                            )
                    );

            List<String> tags =
                    extractStringList(
                            structured.get(
                                    "tags"
                            )
                    );

            return new StructuredData(
                    entities,
                    tags
            );

        } catch (Exception error) {
            System.err.println(
                    "⚠️ structuredAnalysis 파싱 실패: contentId="
                            + content.getId()
                            + " / "
                            + error.getMessage()
            );

            return new StructuredData(
                    List.of(),
                    List.of()
            );
        }
    }


    private List<StructuredEntity> extractEntityDetails(
            Object rawDetails
    ) {
        if (!(rawDetails
                instanceof List<?> details)) {
            return List.of();
        }

        List<StructuredEntity> result =
                new ArrayList<>();

        for (Object rawDetail : details) {
            if (!(rawDetail
                    instanceof Map<?, ?> detail)) {
                continue;
            }

            String name =
                    stringValue(
                            detail.get("name")
                    ).trim();

            String type =
                    normalizeType(
                            stringValue(
                                    detail.get("type")
                            )
                    );

            double confidence =
                    confidenceValue(
                            detail.get(
                                    "confidence"
                            )
                    );

            if (name.isBlank()
                    || type == null) {
                continue;
            }

            result.add(
                    new StructuredEntity(
                            name,
                            type,
                            confidence
                    )
            );
        }

        return result;
    }


    private List<String> extractStringList(
            Object rawValue
    ) {
        if (!(rawValue
                instanceof List<?> values)) {
            return List.of();
        }

        List<String> result =
                new ArrayList<>();

        for (Object value : values) {
            String text =
                    stringValue(value)
                            .trim();

            if (!text.isBlank()) {
                result.add(text);
            }
        }

        return result;
    }


    private String safeTitle(
            String value
    ) {
        if (value == null
                || value.isBlank()) {
            return "저장 콘텐츠";
        }

        return value.trim();
    }


    private String safeSummary(
            String value
    ) {
        if (value == null) {
            return "";
        }

        return value.trim();
    }


    private String normalizeType(
            String value
    ) {
        if (value == null) {
            return null;
        }

        String normalized =
                value.trim()
                        .toUpperCase(
                                Locale.ROOT
                        );

        if (normalized.isBlank()) {
            return null;
        }

        return normalized;
    }


    private String normalizeName(
            String value
    ) {
        if (value == null) {
            return "";
        }

        return Normalizer
                .normalize(
                        value,
                        Normalizer.Form.NFKC
                )
                .trim()
                .replaceAll(
                        "\\s+",
                        " "
                )
                .toLowerCase(
                        Locale.ROOT
                );
    }


    private String stringValue(
            Object value
    ) {
        return value == null
                ? ""
                : String.valueOf(value);
    }


    private double confidenceValue(
            Object value
    ) {
        if (value instanceof Number number) {
            return clamp(
                    number.doubleValue()
            );
        }

        try {
            return clamp(
                    Double.parseDouble(
                            stringValue(value)
                    )
            );
        } catch (NumberFormatException ignored) {
            return 0.0;
        }
    }


    private double clamp(
            double value
    ) {
        return Math.max(
                0.0,
                Math.min(
                        1.0,
                        value
                )
        );
    }


    private double roundConfidence(
            double value
    ) {
        return Math.round(
                value * 100.0
        ) / 100.0;
    }


    private record StructuredEntity(
            String name,
            String type,
            double confidence
    ) {
    }


    private record StructuredData(
            List<StructuredEntity> entities,
            List<String> tags
    ) {
    }


    private static final class ConnectionAccumulator {

        private final String entity;
        private final String type;
        private final Set<Long> contentIds =
                new HashSet<>();

        private double maxConfidence = 0.0;


        private ConnectionAccumulator(
                String entity,
                String type
        ) {
            this.entity =
                    entity.trim();

            this.type =
                    type;
        }


        private void add(
                Long contentId,
                double confidence
        ) {
            if (contentId != null) {
                contentIds.add(
                        contentId
                );
            }

            maxConfidence =
                    Math.max(
                            maxConfidence,
                            confidence
                    );
        }


        private String entity() {
            return entity;
        }


        private String type() {
            return type;
        }


        private long count() {
            return contentIds.size();
        }


        private double confidence() {
            return maxConfidence;
        }
    }


    private static final class RelatedEntityAccumulator {

        private final String entity;
        private final String type;
        private final Set<Long> contentIds =
                new HashSet<>();


        private RelatedEntityAccumulator(
                String entity,
                String type
        ) {
            this.entity =
                    entity.trim();

            this.type =
                    type;
        }


        private void add(
                Long contentId
        ) {
            if (contentId != null) {
                contentIds.add(
                        contentId
                );
            }
        }


        private String entity() {
            return entity;
        }


        private String type() {
            return type;
        }


        private long count() {
            return contentIds.size();
        }
    }
}
