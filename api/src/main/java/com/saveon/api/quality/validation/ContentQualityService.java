package com.saveon.api.quality.validation;

import com.saveon.api.content.Content;
import com.saveon.api.content.ContentRepository;
import com.saveon.api.quality.canonical.CanonicalEntity;
import com.saveon.api.quality.canonical.CanonicalEntityService;
import com.saveon.api.quality.validation.dto.ContentQualityResponse;
import com.saveon.api.quality.validation.dto.ContentQualityWarning;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.time.DateTimeException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class ContentQualityService {

    private static final double MIN_CONFIDENCE = 0.65;

    private static final Pattern KOREAN_DATE =
            Pattern.compile(
                    "(?:(\\d{4})년\\s*)?(\\d{1,2})월\\s*(\\d{1,2})일"
            );

    private static final Pattern ISO_DATE =
            Pattern.compile(
                    "(\\d{4})-(\\d{2})-(\\d{2})"
            );

    private final ContentRepository contentRepository;
    private final CanonicalEntityService canonicalEntityService;
    private final JsonMapper jsonMapper;

    public ContentQualityService(
            ContentRepository contentRepository,
            CanonicalEntityService canonicalEntityService
    ) {
        this.contentRepository = contentRepository;
        this.canonicalEntityService = canonicalEntityService;
        this.jsonMapper = JsonMapper.builder().build();
    }


    public ContentQualityResponse validate(
            Long contentId
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

        List<ContentQualityWarning> warnings =
                validateContent(content);

        boolean hasError =
                warnings.stream()
                        .anyMatch(warning ->
                                "ERROR".equals(
                                        warning.severity()
                                )
                        );

        return new ContentQualityResponse(
                !hasError,
                !warnings.isEmpty(),
                warnings
        );
    }


    public List<ContentQualityWarning> validateContent(
            Content content
    ) {
        List<ContentQualityWarning> warnings =
                new ArrayList<>();

        String raw =
                content.getStructuredAnalysis();

        if (raw == null || raw.isBlank()) {
            warnings.add(
                    warning(
                            "MISSING_STRUCTURED_ANALYSIS",
                            "structuredAnalysis",
                            "WARN",
                            "구조화 분석 결과가 없어 자동 검증을 충분히 수행할 수 없어요."
                    )
            );

            return warnings;
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> structured =
                    jsonMapper.readValue(
                            raw,
                            Map.class
                    );

            List<Map<String, Object>> entities =
                    parseMaps(
                            structured.get("entityDetails")
                    );

            String primaryCategory =
                    stringValue(
                            structured.get("primaryCategory")
                    ).trim();

            boolean strongPlace = false;

            Map<String, String> seenTypes =
                    new HashMap<>();

            for (Map<String, Object> entity : entities) {
                String name =
                        stringValue(
                                entity.get("name")
                        ).trim();

                String type =
                        normalizeType(
                                stringValue(
                                        entity.get("type")
                                )
                        );

                double confidence =
                        numberValue(
                                entity.get("confidence")
                        );

                if (confidence < MIN_CONFIDENCE) {
                    warnings.add(
                            warning(
                                    "LOW_CONFIDENCE_ENTITY",
                                    "entityDetails",
                                    "WARN",
                                    name.isBlank()
                                            ? "확신도가 낮은 엔티티가 있어요."
                                            : "“" + name + "” 엔티티의 AI 확신도가 낮아요."
                            )
                    );
                }

                if ("PLACE".equals(type)
                        && confidence >= MIN_CONFIDENCE) {
                    strongPlace = true;
                }

                String normalized =
                        canonicalEntityService
                                .normalize(name);

                if (!normalized.isBlank()) {
                    String seen =
                            seenTypes.putIfAbsent(
                                    normalized,
                                    type
                            );

                    if (seen != null
                            && !seen.equals(type)) {
                        warnings.add(
                                warning(
                                        "ENTITY_TYPE_CONFLICT",
                                        "entityDetails",
                                        "WARN",
                                        "같은 엔티티가 서로 다른 타입으로 분석됐어요: "
                                                + name
                                )
                        );
                    }
                }

                Optional<CanonicalEntity> canonical =
                        canonicalEntityService.find(
                                name
                        );

                if (canonical.isPresent()
                        && !canonical.get()
                        .getEntityType()
                        .equals(type)) {
                    warnings.add(
                            warning(
                                    "CANONICAL_TYPE_CONFLICT",
                                    "entityDetails",
                                    "WARN",
                                    "이전에 검증된 타입과 현재 분석이 달라요: "
                                            + name
                            )
                    );
                }
            }

            if ("장소/여행".equals(primaryCategory)
                    && !entities.isEmpty()
                    && !strongPlace) {
                warnings.add(
                        warning(
                                "CATEGORY_ENTITY_CONFLICT",
                                "entityDetails",
                                "WARN",
                                "장소/여행 콘텐츠인데 확실한 PLACE 엔티티가 없어요."
                        )
                );
            }

            for (Map<String, Object> claim :
                    parseMaps(
                            structured.get("claims")
                    )) {
                String type =
                        normalizeType(
                                stringValue(
                                        claim.get("type")
                                )
                        );

                boolean verifiable =
                        booleanValue(
                                claim.get("verifiable")
                        );

                if (!"DATE_TIME".equals(type)
                        || !verifiable) {
                    continue;
                }

                String text =
                        stringValue(
                                claim.get("text")
                        );

                if (containsInvalidDate(text)) {
                    warnings.add(
                            warning(
                                    "INVALID_DATE",
                                    "claims",
                                    "ERROR",
                                    "날짜 형식이 실제 달력에 존재하지 않는 값으로 분석됐어요: "
                                            + text
                            )
                    );
                }
            }

        } catch (Exception error) {
            warnings.add(
                    warning(
                            "VALIDATION_PARSE_ERROR",
                            "structuredAnalysis",
                            "WARN",
                            "AI 구조화 결과를 자동 검증하는 중 파싱 오류가 발생했어요."
                    )
            );
        }

        return warnings;
    }


    private boolean containsInvalidDate(
            String text
    ) {
        Matcher korean =
                KOREAN_DATE.matcher(text);

        while (korean.find()) {
            int year =
                    korean.group(1) != null
                            ? Integer.parseInt(
                            korean.group(1)
                    )
                            : LocalDate.now().getYear();

            int month =
                    Integer.parseInt(
                            korean.group(2)
                    );

            int day =
                    Integer.parseInt(
                            korean.group(3)
                    );

            if (!validDate(
                    year,
                    month,
                    day
            )) {
                return true;
            }
        }

        Matcher iso =
                ISO_DATE.matcher(text);

        while (iso.find()) {
            if (!validDate(
                    Integer.parseInt(
                            iso.group(1)
                    ),
                    Integer.parseInt(
                            iso.group(2)
                    ),
                    Integer.parseInt(
                            iso.group(3)
                    )
            )) {
                return true;
            }
        }

        return false;
    }


    private boolean validDate(
            int year,
            int month,
            int day
    ) {
        try {
            LocalDate.of(
                    year,
                    month,
                    day
            );
            return true;
        } catch (DateTimeException error) {
            return false;
        }
    }


    private List<Map<String, Object>> parseMaps(
            Object rawValue
    ) {
        if (!(rawValue instanceof List<?> values)) {
            return List.of();
        }

        List<Map<String, Object>> result =
                new ArrayList<>();

        for (Object raw : values) {
            if (!(raw instanceof Map<?, ?> map)) {
                continue;
            }

            Map<String, Object> item =
                    new HashMap<>();

            for (Map.Entry<?, ?> entry :
                    map.entrySet()) {
                item.put(
                        String.valueOf(
                                entry.getKey()
                        ),
                        entry.getValue()
                );
            }

            result.add(item);
        }

        return result;
    }


    private ContentQualityWarning warning(
            String type,
            String field,
            String severity,
            String message
    ) {
        return new ContentQualityWarning(
                type,
                field,
                severity,
                message
        );
    }


    private String normalizeType(
            String value
    ) {
        return value == null
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


    private boolean booleanValue(
            Object value
    ) {
        if (value instanceof Boolean bool) {
            return bool;
        }

        return Boolean.parseBoolean(
                stringValue(value)
        );
    }
}
