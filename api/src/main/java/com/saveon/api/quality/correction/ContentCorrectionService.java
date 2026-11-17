package com.saveon.api.quality.correction;

import com.saveon.api.content.Content;
import com.saveon.api.content.ContentRepository;
import com.saveon.api.quality.canonical.CanonicalEntityService;
import com.saveon.api.quality.correction.dto.ActionCorrectionRequest;
import com.saveon.api.quality.correction.dto.ContentCorrectionRequest;
import com.saveon.api.quality.correction.dto.CorrectionStatsResponse;
import com.saveon.api.quality.correction.dto.EntityCorrectionRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.json.JsonMapper;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
public class ContentCorrectionService {

    private static final Set<String> ALLOWED_ENTITY_TYPES =
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

    private static final Set<String> ALLOWED_CATEGORIES =
            Set.of(
                    "장소/여행",
                    "음식/레시피",
                    "제품/쇼핑",
                    "뷰티/패션",
                    "학습/커리어",
                    "건강/운동",
                    "생활정보",
                    "엔터테인먼트",
                    "기타"
            );

    private final ContentRepository contentRepository;
    private final AiCorrectionRepository correctionRepository;
    private final CanonicalEntityService canonicalEntityService;
    private final JsonMapper jsonMapper;

    public ContentCorrectionService(
            ContentRepository contentRepository,
            AiCorrectionRepository correctionRepository,
            CanonicalEntityService canonicalEntityService
    ) {
        this.contentRepository = contentRepository;
        this.correctionRepository = correctionRepository;
        this.canonicalEntityService = canonicalEntityService;
        this.jsonMapper = JsonMapper.builder().build();
    }


    @Transactional
    public Content correctContent(
            Long contentId,
            ContentCorrectionRequest request
    ) {
        Content content =
                contentRepository
                        .findById(contentId)
                        .orElseThrow(
                                () ->
                                        new IllegalArgumentException(
                                                "Content not found: "
                                                        + contentId
                                        )
                        );

        Map<String, Object> structured =
                parseStructured(
                        content.getStructuredAnalysis()
                );

        List<Map<String, Object>> originalEntities =
                parseEntityDetails(
                        structured.get("entityDetails")
                );

        Map<String, Object> originalSnapshot =
                snapshot(content, structured);

        String correctedTitle =
                cleanOrFallback(
                        request.title(),
                        content.getTitle()
                );

        String correctedSummary =
                cleanOrFallback(
                        request.summary(),
                        content.getSummary()
                );

        List<String> correctedCategories =
                cleanList(
                        request.categories(),
                        content.getCategories()
                );

        List<String> correctedKeywords =
                cleanList(
                        request.keywords(),
                        content.getKeywords()
                );

        List<Map<String, Object>> correctedEntityDetails =
                normalizeEntityDetails(
                        request.entityDetails()
                );

        if (correctedEntityDetails.isEmpty()) {
            correctedEntityDetails =
                    originalEntities;
        }

        List<String> correctedEntityNames =
                correctedEntityDetails
                        .stream()
                        .map(item ->
                                stringValue(
                                        item.get("name")
                                )
                        )
                        .filter(value ->
                                !value.isBlank()
                        )
                        .distinct()
                        .toList();

        if (!correctedCategories.isEmpty()) {
            structured.put(
                    "primaryCategory",
                    correctedCategories.get(0)
            );
        }

        structured.put(
                "entityDetails",
                correctedEntityDetails
        );

        String correctedStructured;
        try {
            correctedStructured =
                    jsonMapper.writeValueAsString(
                            structured
                    );
        } catch (Exception error) {
            throw new IllegalStateException(
                    "수정된 structuredAnalysis 직렬화 실패",
                    error
            );
        }

        content.applyUserCorrection(
                correctedTitle,
                correctedSummary,
                correctedCategories,
                correctedKeywords,
                correctedEntityNames,
                correctedStructured
        );

        Content saved =
                contentRepository.save(content);

        Map<String, Object> correctedSnapshot =
                snapshot(
                        saved,
                        structured
                );

        List<String> errorTypes =
                detectErrors(
                        originalSnapshot,
                        correctedSnapshot,
                        originalEntities,
                        correctedEntityDetails
                );

        String aiJson =
                toJson(originalSnapshot);

        String correctedJson =
                toJson(correctedSnapshot);

        for (String errorType : errorTypes) {
            correctionRepository.save(
                    new AiCorrection(
                            contentId,
                            "DETAIL_EDIT",
                            "CONTENT_ANALYSIS",
                            aiJson,
                            correctedJson,
                            errorType
                    )
            );
        }

        for (int index = 0;
             index < correctedEntityDetails.size();
             index++) {

            Map<String, Object> correctedEntity =
                    correctedEntityDetails.get(index);

            String correctedName =
                    stringValue(
                            correctedEntity.get("name")
                    ).trim();

            String correctedType =
                    normalizeType(
                            stringValue(
                                    correctedEntity.get("type")
                            )
                    );

            String originalName = "";
            String originalType = "";

            if (index < originalEntities.size()) {
                Map<String, Object> originalEntity =
                        originalEntities.get(index);

                originalName =
                        stringValue(
                                originalEntity.get("name")
                        ).trim();

                originalType =
                        normalizeType(
                                stringValue(
                                        originalEntity.get("type")
                                )
                        );
            }

            boolean actuallyCorrected =
                    index >= originalEntities.size()
                            || !correctedName.equals(originalName)
                            || !correctedType.equals(originalType);

            if (!actuallyCorrected
                    || correctedName.isBlank()
                    || !ALLOWED_ENTITY_TYPES.contains(
                    correctedType
            )) {
                continue;
            }

            canonicalEntityService.upsert(
                    correctedName,
                    correctedName,
                    correctedType,
                    "USER_CORRECTION"
            );

            if (!originalName.isBlank()
                    && !originalName.equals(correctedName)) {
                canonicalEntityService.upsert(
                        originalName,
                        correctedName,
                        correctedType,
                        "USER_CORRECTION"
                );
            }
        }

        return saved;
    }


    public void logActionCorrection(
            ActionCorrectionRequest request
    ) {
        if (request == null) {
            return;
        }

        String original =
                clean(
                        request.aiValue(),
                        500
                );

        String corrected =
                clean(
                        request.correctedValue(),
                        500
                );

        if (original.isBlank()
                || corrected.isBlank()
                || original.equals(corrected)) {
            return;
        }

        String errorType =
                clean(
                        request.errorType(),
                        80
                );

        correctionRepository.save(
                new AiCorrection(
                        request.contentId(),
                        "ACTION_CONFIRMATION",
                        clean(
                                request.fieldName(),
                                80
                        ),
                        original,
                        corrected,
                        errorType.isBlank()
                                ? "OTHER"
                                : errorType
                )
        );

        if ("MAP_QUERY".equals(
                clean(
                        request.fieldName(),
                        80
                )
        )) {
            canonicalEntityService.upsert(
                    original,
                    corrected,
                    "PLACE",
                    "ACTION_CONFIRMATION"
            );

            canonicalEntityService.upsert(
                    corrected,
                    corrected,
                    "PLACE",
                    "ACTION_CONFIRMATION"
            );
        }
    }


    public List<AiCorrection> history(
            Long contentId
    ) {
        return correctionRepository
                .findByContentIdOrderByCreatedAtDesc(
                        contentId
                );
    }


    public CorrectionStatsResponse stats() {
        Map<String, Long> counts =
                new LinkedHashMap<>();

        for (Object[] row :
                correctionRepository.countByErrorType()) {
            if (row.length < 2) {
                continue;
            }

            counts.put(
                    String.valueOf(row[0]),
                    ((Number) row[1]).longValue()
            );
        }

        return new CorrectionStatsResponse(
                correctionRepository.count(),
                counts
        );
    }


    private Map<String, Object> snapshot(
            Content content,
            Map<String, Object> structured
    ) {
        Map<String, Object> value =
                new LinkedHashMap<>();

        value.put(
                "title",
                content.getTitle()
        );
        value.put(
                "summary",
                content.getSummary()
        );
        value.put(
                "categories",
                new ArrayList<>(
                        content.getCategories()
                )
        );
        value.put(
                "keywords",
                new ArrayList<>(
                        content.getKeywords()
                )
        );
        value.put(
                "entities",
                new ArrayList<>(
                        content.getEntities()
                )
        );
        value.put(
                "structured",
                new LinkedHashMap<>(structured)
        );

        return value;
    }


    private List<String> detectErrors(
            Map<String, Object> original,
            Map<String, Object> corrected,
            List<Map<String, Object>> originalEntities,
            List<Map<String, Object>> correctedEntities
    ) {
        LinkedHashSet<String> result =
                new LinkedHashSet<>();

        if (!safeEquals(
                original.get("title"),
                corrected.get("title")
        )) {
            result.add("WRONG_TITLE");
        }

        if (!safeEquals(
                original.get("summary"),
                corrected.get("summary")
        )) {
            result.add("WRONG_SUMMARY");
        }

        if (!safeEquals(
                original.get("categories"),
                corrected.get("categories")
        )) {
            result.add("CATEGORY_MISMATCH");
        }

        if (!safeEquals(
                original.get("keywords"),
                corrected.get("keywords")
        )) {
            result.add("WRONG_KEYWORD");
        }

        if (originalEntities.size()
                != correctedEntities.size()) {
            result.add("MISSING_ENTITY");
        }

        int shared =
                Math.min(
                        originalEntities.size(),
                        correctedEntities.size()
                );

        for (int index = 0; index < shared; index++) {
            Map<String, Object> before =
                    originalEntities.get(index);

            Map<String, Object> after =
                    correctedEntities.get(index);

            String beforeName =
                    stringValue(
                            before.get("name")
                    ).trim();

            String afterName =
                    stringValue(
                            after.get("name")
                    ).trim();

            String beforeType =
                    normalizeType(
                            stringValue(
                                    before.get("type")
                            )
                    );

            String afterType =
                    normalizeType(
                            stringValue(
                                    after.get("type")
                            )
                    );

            if (!beforeName.equals(afterName)) {
                result.add("ENTITY_NAME_ERROR");
            }

            if (!beforeType.equals(afterType)) {
                result.add("ENTITY_TYPE_MISMATCH");
            }
        }

        if (result.isEmpty()) {
            result.add("OTHER");
        }

        return new ArrayList<>(result);
    }


    private List<Map<String, Object>> normalizeEntityDetails(
            List<EntityCorrectionRequest> values
    ) {
        if (values == null) {
            return List.of();
        }

        List<Map<String, Object>> result =
                new ArrayList<>();

        Set<String> seen =
                new LinkedHashSet<>();

        for (EntityCorrectionRequest item : values) {
            if (item == null) {
                continue;
            }

            String name =
                    clean(
                            item.name(),
                            180
                    );

            String type =
                    normalizeType(
                            item.type()
                    );

            if (name.isBlank()
                    || !ALLOWED_ENTITY_TYPES.contains(type)) {
                continue;
            }

            String key =
                    name.toLowerCase(Locale.ROOT)
                            + "|"
                            + type;

            if (!seen.add(key)) {
                continue;
            }

            Map<String, Object> entity =
                    new LinkedHashMap<>();

            entity.put("name", name);
            entity.put("type", type);
            entity.put("confidence", 1.0);

            result.add(entity);

            if (result.size() >= 20) {
                break;
            }
        }

        return result;
    }


    private List<Map<String, Object>> parseEntityDetails(
            Object rawValue
    ) {
        if (!(rawValue instanceof List<?> values)) {
            return List.of();
        }

        List<Map<String, Object>> result =
                new ArrayList<>();

        for (Object raw : values) {
            if (!(raw instanceof Map<?, ?> item)) {
                continue;
            }

            Map<String, Object> entity =
                    new LinkedHashMap<>();

            entity.put(
                    "name",
                    stringValue(
                            item.get("name")
                    )
            );

            entity.put(
                    "type",
                    normalizeType(
                            stringValue(
                                    item.get("type")
                            )
                    )
            );

            entity.put(
                    "confidence",
                    numberValue(
                            item.get("confidence")
                    )
            );

            result.add(entity);
        }

        return result;
    }


    private Map<String, Object> parseStructured(
            String raw
    ) {
        if (raw == null || raw.isBlank()) {
            return new LinkedHashMap<>();
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> parsed =
                    jsonMapper.readValue(
                            raw,
                            Map.class
                    );

            return new LinkedHashMap<>(parsed);

        } catch (Exception error) {
            throw new IllegalStateException(
                    "structuredAnalysis 파싱 실패",
                    error
            );
        }
    }


    private List<String> cleanList(
            List<String> values,
            List<String> fallback
    ) {
        if (values == null) {
            return fallback != null
                    ? new ArrayList<>(fallback)
                    : List.of();
        }

        LinkedHashSet<String> result =
                new LinkedHashSet<>();

        for (String value : values) {
            String cleaned =
                    clean(value, 100);

            if (!cleaned.isBlank()
                    && ALLOWED_CATEGORIES.contains(cleaned)) {
                result.add(cleaned);
            }
        }

        if (result.isEmpty()
                && fallback != null) {
            result.addAll(fallback);
        }

        return new ArrayList<>(result);
    }


    private String cleanOrFallback(
            String value,
            String fallback
    ) {
        String cleaned =
                clean(value, 1000);

        return cleaned.isBlank()
                ? stringValue(fallback)
                : cleaned;
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


    private String normalizeType(
            String value
    ) {
        return value == null || value.isBlank()
                ? "OTHER"
                : value
                .trim()
                .toUpperCase(Locale.ROOT);
    }


    private String stringValue(
            Object value
    ) {
        return value == null
                ? ""
                : String.valueOf(value);
    }


    private double numberValue(
            Object value
    ) {
        if (value instanceof Number number) {
            return number.doubleValue();
        }

        try {
            return Double.parseDouble(
                    stringValue(value)
            );
        } catch (Exception ignored) {
            return 0.0;
        }
    }


    private boolean safeEquals(
            Object left,
            Object right
    ) {
        return String.valueOf(left)
                .equals(
                        String.valueOf(right)
                );
    }


    private String toJson(
            Object value
    ) {
        try {
            return jsonMapper.writeValueAsString(
                    value
            );
        } catch (Exception error) {
            return String.valueOf(value);
        }
    }
}
