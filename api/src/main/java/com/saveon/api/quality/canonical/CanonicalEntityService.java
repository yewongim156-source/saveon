package com.saveon.api.quality.canonical;

import com.saveon.api.content.Content;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

@Service
public class CanonicalEntityService {

    private static final Set<String> ALLOWED_TYPES =
            Set.of(
                    "PLACE",
                    "PRODUCT",
                    "BRAND",
                    "PERSON",
                    "SERVICE",
                    "EVENT",
                    "DATE",
                    "OTHER"
            );

    private final CanonicalEntityRepository repository;
    private final JsonMapper jsonMapper;

    public CanonicalEntityService(
            CanonicalEntityRepository repository
    ) {
        this.repository = repository;
        this.jsonMapper = JsonMapper.builder().build();
    }


    public List<CanonicalEntity> findAll() {
        return repository.findAll();
    }


    public Optional<CanonicalEntity> find(
            String name
    ) {
        String normalized = normalize(name);

        if (normalized.isBlank()) {
            return Optional.empty();
        }

        return repository.findByNormalizedName(
                normalized
        );
    }


    public CanonicalEntity upsert(
            String lookupName,
            String displayName,
            String entityType,
            String source
    ) {
        String normalized =
                normalize(lookupName);

        String safeDisplay =
                clean(displayName, 180);

        String safeType =
                normalizeType(entityType);

        String safeSource =
                clean(source, 40);

        if (normalized.isBlank()
                || safeDisplay.isBlank()
                || !ALLOWED_TYPES.contains(safeType)) {
            throw new IllegalArgumentException(
                    "Canonical entity 값이 올바르지 않습니다."
            );
        }

        CanonicalEntity entity =
                repository
                        .findByNormalizedName(normalized)
                        .orElseGet(
                                () ->
                                        new CanonicalEntity(
                                                normalized,
                                                safeDisplay,
                                                safeType,
                                                safeSource.isBlank()
                                                        ? "USER_CORRECTION"
                                                        : safeSource
                                        )
                        );

        if (entity.getId() != null) {
            entity.verifyAgain(
                    safeDisplay,
                    safeType,
                    safeSource.isBlank()
                            ? entity.getVerificationSource()
                            : safeSource
            );
        }

        return repository.save(entity);
    }


    public boolean applyKnownEntities(
            Content content
    ) {
        String raw =
                content.getStructuredAnalysis();

        if (raw == null || raw.isBlank()) {
            return false;
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> structured =
                    jsonMapper.readValue(
                            raw,
                            Map.class
                    );

            Object rawDetails =
                    structured.get("entityDetails");

            if (!(rawDetails instanceof List<?> details)) {
                return false;
            }

            List<Map<String, Object>> corrected =
                    new ArrayList<>();

            List<String> entityNames =
                    new ArrayList<>();

            boolean changed = false;

            for (Object rawDetail : details) {
                if (!(rawDetail instanceof Map<?, ?> detail)) {
                    continue;
                }

                String originalName =
                        stringValue(
                                detail.get("name")
                        ).trim();

                String originalType =
                        normalizeType(
                                stringValue(
                                        detail.get("type")
                                )
                        );

                double confidence =
                        confidenceValue(
                                detail.get("confidence")
                        );

                String finalName = originalName;
                String finalType = originalType;
                double finalConfidence = confidence;

                Optional<CanonicalEntity> canonical =
                        find(originalName);

                if (canonical.isPresent()) {
                    CanonicalEntity known =
                            canonical.get();

                    finalName =
                            known.getDisplayName();

                    finalType =
                            known.getEntityType();

                    finalConfidence =
                            Math.max(
                                    confidence,
                                    0.99
                            );

                    if (!finalName.equals(originalName)
                            || !finalType.equals(originalType)) {
                        changed = true;
                    }
                }

                Map<String, Object> value =
                        new LinkedHashMap<>();

                value.put("name", finalName);
                value.put("type", finalType);
                value.put(
                        "confidence",
                        finalConfidence
                );

                corrected.add(value);

                if (!finalName.isBlank()
                        && !entityNames.contains(finalName)) {
                    entityNames.add(finalName);
                }
            }

            if (!changed) {
                return false;
            }

            structured.put(
                    "entityDetails",
                    corrected
            );

            String correctedJson =
                    jsonMapper.writeValueAsString(
                            structured
                    );

            content.applySystemCorrection(
                    content.getTitle(),
                    content.getSummary(),
                    content.getCategories(),
                    content.getKeywords(),
                    entityNames,
                    correctedJson
            );

            return true;

        } catch (Exception error) {
            System.err.println(
                    "⚠️ Canonical entity 적용 실패: "
                            + error.getMessage()
            );

            return false;
        }
    }


    public String normalize(
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
                .replaceAll("\\s+", " ")
                .toLowerCase(Locale.ROOT);
    }


    private String normalizeType(
            String value
    ) {
        if (value == null || value.isBlank()) {
            return "OTHER";
        }

        return value
                .trim()
                .toUpperCase(Locale.ROOT);
    }


    private String clean(
            String value,
            int max
    ) {
        if (value == null) {
            return "";
        }

        String cleaned =
                value
                        .trim()
                        .replaceAll("\\s+", " ");

        return cleaned.length() <= max
                ? cleaned
                : cleaned.substring(0, max);
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
            return Math.max(
                    0.0,
                    Math.min(
                            1.0,
                            number.doubleValue()
                    )
            );
        }

        try {
            return Math.max(
                    0.0,
                    Math.min(
                            1.0,
                            Double.parseDouble(
                                    stringValue(value)
                            )
                    )
            );
        } catch (Exception ignored) {
            return 0.0;
        }
    }
}
