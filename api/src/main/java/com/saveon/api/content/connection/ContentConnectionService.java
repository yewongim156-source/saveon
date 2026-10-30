package com.saveon.api.content.connection;

import com.saveon.api.content.Content;
import com.saveon.api.content.ContentRepository;
import com.saveon.api.content.ContentStatus;
import com.saveon.api.content.connection.dto.ContentConnectionResponse;
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

    private static final Set<String> CONNECTABLE_TYPES = Set.of(
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
        this.contentRepository = contentRepository;
        this.jsonMapper = JsonMapper.builder().build();
    }

    public List<ContentConnectionResponse> findConnections(
            String requestedType,
            Integer requestedLimit
    ) {
        String typeFilter = normalizeType(requestedType);

        int limit = requestedLimit == null
                ? DEFAULT_LIMIT
                : Math.max(1, Math.min(requestedLimit, MAX_LIMIT));

        Map<String, ConnectionAccumulator> groups = new HashMap<>();

        for (Content content : contentRepository.findAll()) {
            if (content.getStatus() != ContentStatus.COMPLETED) {
                continue;
            }

            Set<String> seenInContent = new HashSet<>();

            for (StructuredEntity entity : extractEntities(content)) {
                if (!CONNECTABLE_TYPES.contains(entity.type())) {
                    continue;
                }

                if (entity.confidence() < MIN_CONFIDENCE) {
                    continue;
                }

                if (typeFilter != null && !typeFilter.equals(entity.type())) {
                    continue;
                }

                String normalizedName = normalizeName(entity.name());
                if (normalizedName.isBlank()) {
                    continue;
                }

                String key = entity.type() + "|" + normalizedName;

                // 같은 콘텐츠 안에서 같은 엔티티가 여러 번 추출돼도 1회만 카운트한다.
                if (!seenInContent.add(key)) {
                    continue;
                }

                ConnectionAccumulator group = groups.computeIfAbsent(
                        key,
                        ignored -> new ConnectionAccumulator(
                                entity.name(),
                                entity.type()
                        )
                );

                group.add(content.getId(), entity.confidence());
            }
        }

        return groups.values()
                .stream()
                .filter(group -> group.count() >= 2)
                .sorted(
                        Comparator
                                .comparingLong(ConnectionAccumulator::count)
                                .reversed()
                                .thenComparing(
                                        Comparator.comparingDouble(
                                                ConnectionAccumulator::confidence
                                        ).reversed()
                                )
                                .thenComparing(ConnectionAccumulator::entity)
                )
                .limit(limit)
                .map(group -> new ContentConnectionResponse(
                        group.entity(),
                        group.type(),
                        group.count(),
                        roundConfidence(group.confidence())
                ))
                .toList();
    }

    public List<Content> findConnectedContents(
            String requestedType,
            String requestedEntity
    ) {
        String type = normalizeType(requestedType);

        if (type == null || !CONNECTABLE_TYPES.contains(type)) {
            return List.of();
        }

        String entity = normalizeName(requestedEntity);
        if (entity.isBlank()) {
            return List.of();
        }

        List<Content> matches = new ArrayList<>();

        for (Content content : contentRepository.findAll()) {
            if (content.getStatus() != ContentStatus.COMPLETED) {
                continue;
            }

            boolean matched = extractEntities(content)
                    .stream()
                    .anyMatch(item ->
                            type.equals(item.type())
                                    && item.confidence() >= MIN_CONFIDENCE
                                    && entity.equals(normalizeName(item.name()))
                    );

            if (matched) {
                matches.add(content);
            }
        }

        matches.sort(
                Comparator.comparing(
                                Content::getCreatedAt,
                                Comparator.nullsLast(Comparator.naturalOrder())
                        )
                        .reversed()
        );

        return matches;
    }

    private List<StructuredEntity> extractEntities(Content content) {
        String raw = content.getStructuredAnalysis();

        if (raw == null || raw.isBlank()) {
            return List.of();
        }

        try {
            Map<?, ?> structured = jsonMapper.readValue(raw, Map.class);
            Object rawDetails = structured.get("entityDetails");

            if (!(rawDetails instanceof List<?> details)) {
                return List.of();
            }

            List<StructuredEntity> result = new ArrayList<>();

            for (Object rawDetail : details) {
                if (!(rawDetail instanceof Map<?, ?> detail)) {
                    continue;
                }

                String name = stringValue(detail.get("name")).trim();
                String type = normalizeType(stringValue(detail.get("type")));
                double confidence = confidenceValue(detail.get("confidence"));

                if (name.isBlank() || type == null) {
                    continue;
                }

                result.add(new StructuredEntity(name, type, confidence));
            }

            return result;
        } catch (Exception error) {
            System.err.println(
                    "⚠️ structuredAnalysis 파싱 실패: contentId="
                            + content.getId()
                            + " / "
                            + error.getMessage()
            );
            return List.of();
        }
    }

    private String normalizeType(String value) {
        if (value == null) {
            return null;
        }

        String normalized = value.trim().toUpperCase(Locale.ROOT);
        return normalized.isBlank() ? null : normalized;
    }

    private String normalizeName(String value) {
        if (value == null) {
            return "";
        }

        return Normalizer
                .normalize(value, Normalizer.Form.NFKC)
                .trim()
                .replaceAll("\\s+", " ")
                .toLowerCase(Locale.ROOT);
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private double confidenceValue(Object value) {
        if (value instanceof Number number) {
            return clamp(number.doubleValue());
        }

        try {
            return clamp(Double.parseDouble(stringValue(value)));
        } catch (NumberFormatException ignored) {
            return 0.0;
        }
    }

    private double clamp(double value) {
        return Math.max(0.0, Math.min(1.0, value));
    }

    private double roundConfidence(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private record StructuredEntity(
            String name,
            String type,
            double confidence
    ) {
    }

    private static final class ConnectionAccumulator {
        private final String entity;
        private final String type;
        private final Set<Long> contentIds = new HashSet<>();
        private double maxConfidence = 0.0;

        private ConnectionAccumulator(
                String entity,
                String type
        ) {
            this.entity = entity.trim();
            this.type = type;
        }

        private void add(Long contentId, double confidence) {
            if (contentId != null) {
                contentIds.add(contentId);
            }
            maxConfidence = Math.max(maxConfidence, confidence);
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
}
