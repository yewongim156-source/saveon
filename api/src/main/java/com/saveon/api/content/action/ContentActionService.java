package com.saveon.api.content.action;

import com.saveon.api.action.ActionAgentClient;
import com.saveon.api.action.AiActionItemResponse;
import com.saveon.api.action.AiActionPlanResponse;
import com.saveon.api.content.Content;
import com.saveon.api.content.ContentStatus;
import com.saveon.api.content.ContentService;
import com.saveon.api.content.action.dto.ContentActionItemResponse;
import com.saveon.api.content.action.dto.ContentActionPlanResponse;
import com.saveon.api.content.connection.dto.ContentBundleResponse;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
public class ContentActionService {

    private static final double MIN_CONFIDENCE = 0.65;

    private static final Set<String> ALLOWED_KINDS =
            Set.of(
                    "MAP_SEARCH",
                    "WEB_SEARCH",
                    "COMPARE_SEARCH",
                    "CALENDAR_ADD",
                    "CHECKLIST_CREATE"
            );

    private static final Set<String> SEARCH_KINDS =
            Set.of(
                    "MAP_SEARCH",
                    "WEB_SEARCH",
                    "COMPARE_SEARCH"
            );

    private final ActionAgentClient actionAgentClient;
    private final ContentService contentService;
    private final JsonMapper jsonMapper;

    public ContentActionService(
            ActionAgentClient actionAgentClient,
            ContentService contentService
    ) {
        this.actionAgentClient = actionAgentClient;
        this.contentService = contentService;
        this.jsonMapper = JsonMapper.builder().build();
    }


    public ContentActionPlanResponse plan(
            ContentBundleResponse bundle
    ) {
        ContentActionPlanResponse fallback =
                buildBundleFallback(bundle);

        if (bundle == null
                || bundle.entity() == null
                || bundle.entity().isBlank()) {
            return fallback;
        }

        try {
            AiActionPlanResponse ai =
                    actionAgentClient.plan(bundle);

            List<ContentActionItemResponse> actions =
                    normalizeActions(
                            ai != null ? ai.actions() : null,
                            bundleHasPlace(bundle),
                            bundleHasComparable(bundle),
                            hasDateFact(bundle),
                            isChecklistEligible(bundle)
                    );

            if (actions.isEmpty()) {
                return fallback;
            }

            return new ContentActionPlanResponse(
                    "AGENT",
                    actions
            );

        } catch (Exception error) {
            System.err.println(
                    "⚠️ Bundle Action Agent 실패 - 기본 행동으로 대체: "
                            + error.getMessage()
            );
            return fallback;
        }
    }


    public ContentActionPlanResponse planSingleContent(
            Long contentId
    ) {
        Content content =
                contentService.findById(contentId);

        if (content.getStatus() != ContentStatus.COMPLETED) {
            return new ContentActionPlanResponse(
                    "RULE_BASED",
                    List.of()
            );
        }

        SingleActionContext context =
                buildSingleContext(content);

        ContentActionPlanResponse fallback =
                buildSingleFallback(content, context);

        try {
            AiActionPlanResponse ai =
                    actionAgentClient.plan(
                            buildSingleAgentRequest(
                                    content,
                                    context
                            )
                    );

            List<ContentActionItemResponse> actions =
                    normalizeActions(
                            ai != null ? ai.actions() : null,
                            context.hasPlace(),
                            context.hasComparable(),
                            context.hasDateFact(),
                            context.checklistEligible()
                    );

            if (actions.isEmpty()) {
                return fallback;
            }

            return new ContentActionPlanResponse(
                    "AGENT",
                    actions
            );

        } catch (Exception error) {
            System.err.println(
                    "⚠️ Single Content Action Agent 실패 - 기본 행동으로 대체: "
                            + error.getMessage()
            );
            return fallback;
        }
    }


    private Map<String, Object> buildSingleAgentRequest(
            Content content,
            SingleActionContext context
    ) {
        Map<String, Object> request =
                new LinkedHashMap<>();

        request.put("contextType", "SINGLE_CONTENT");
        request.put("entity", context.primaryEntity());
        request.put("type", context.primaryType());
        request.put("count", 1);
        request.put("title", safe(content.getTitle()));
        request.put("summary", safe(content.getSummary()));
        request.put("categories", content.getCategories());
        request.put("commonKeywords", content.getKeywords());
        request.put("commonTags", context.tags());
        request.put("contentTypes",
                context.contentType().isBlank()
                        ? List.of()
                        : List.of(context.contentType())
        );
        request.put("relatedEntities", List.of());
        request.put("entityDetails", context.entityDetails());

        request.put(
                "highlights",
                List.of(
                        Map.of(
                                "contentId", content.getId(),
                                "title", safe(content.getTitle()),
                                "summary", safe(content.getSummary())
                        )
                )
        );

        request.put("actionFacts", context.actionFacts());
        request.put("synthesis", null);

        return request;
    }


    private SingleActionContext buildSingleContext(
            Content content
    ) {
        if (content.getStructuredAnalysis() == null
                || content.getStructuredAnalysis().isBlank()) {
            return fallbackSingleContext(content);
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> structured =
                    jsonMapper.readValue(
                            content.getStructuredAnalysis(),
                            Map.class
                    );

            List<Map<String, Object>> entityDetails =
                    parseEntityDetails(
                            structured.get("entityDetails")
                    );

            List<Map<String, Object>> actionFacts =
                    parseActionFacts(
                            content.getId(),
                            structured.get("claims")
                    );

            List<String> tags =
                    parseStringList(
                            structured.get("tags")
                    );

            String contentType =
                    normalizeType(
                            stringValue(
                                    structured.get("contentType")
                            )
                    );

            String primaryEntity = "";
            String primaryType = "CONTENT";
            double bestConfidence = -1.0;

            boolean hasPlace = false;
            boolean hasComparable = false;

            for (Map<String, Object> entity : entityDetails) {
                String name =
                        stringValue(entity.get("name")).trim();

                String type =
                        normalizeType(
                                stringValue(entity.get("type"))
                        );

                double confidence =
                        numberValue(
                                entity.get("confidence")
                        );

                if (confidence < MIN_CONFIDENCE
                        || name.isBlank()) {
                    continue;
                }

                if ("PLACE".equals(type)) {
                    hasPlace = true;
                }

                if ("PRODUCT".equals(type)
                        || "BRAND".equals(type)) {
                    hasComparable = true;
                }

                if (confidence > bestConfidence) {
                    primaryEntity = name;
                    primaryType = type;
                    bestConfidence = confidence;
                }
            }

            if (primaryEntity.isBlank()) {
                if (content.getEntities() != null
                        && !content.getEntities().isEmpty()) {
                    primaryEntity =
                            content.getEntities().get(0);
                } else {
                    primaryEntity =
                            safe(content.getTitle());
                }
            }

            boolean hasDateFact =
                    actionFacts.stream()
                            .anyMatch(item ->
                                    "DATE_TIME".equals(
                                            normalizeType(
                                                    stringValue(
                                                            item.get("type")
                                                    )
                                            )
                                    )
                            );

            boolean checklistEligible =
                    "RECIPE".equals(contentType)
                            || "HOW_TO".equals(contentType)
                            || content.getCategories()
                            .stream()
                            .anyMatch("음식/레시피"::equals);

            return new SingleActionContext(
                    primaryEntity,
                    primaryType,
                    contentType,
                    tags,
                    entityDetails,
                    actionFacts,
                    hasPlace,
                    hasComparable,
                    hasDateFact,
                    checklistEligible
            );

        } catch (Exception error) {
            System.err.println(
                    "⚠️ 단일 콘텐츠 structuredAnalysis 파싱 실패: "
                            + error.getMessage()
            );

            return fallbackSingleContext(content);
        }
    }


    private SingleActionContext fallbackSingleContext(
            Content content
    ) {
        String primaryEntity =
                content.getEntities() != null
                        && !content.getEntities().isEmpty()
                        ? content.getEntities().get(0)
                        : safe(content.getTitle());

        return new SingleActionContext(
                primaryEntity,
                "CONTENT",
                "",
                List.of(),
                List.of(),
                List.of(),
                false,
                false,
                false,
                false
        );
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

            String name =
                    stringValue(item.get("name")).trim();

            String type =
                    normalizeType(
                            stringValue(item.get("type"))
                    );

            double confidence =
                    numberValue(item.get("confidence"));

            if (name.isBlank()) {
                continue;
            }

            Map<String, Object> value =
                    new LinkedHashMap<>();

            value.put("name", name);
            value.put("type", type);
            value.put("confidence", confidence);

            result.add(value);

            if (result.size() >= 12) {
                break;
            }
        }

        return result;
    }


    private List<Map<String, Object>> parseActionFacts(
            Long contentId,
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

            String text =
                    stringValue(item.get("text")).trim();

            String type =
                    normalizeType(
                            stringValue(item.get("type"))
                    );

            boolean verifiable =
                    booleanValue(
                            item.get("verifiable")
                    );

            double confidence =
                    numberValue(item.get("confidence"));

            if (text.isBlank()
                    || !verifiable
                    || confidence < MIN_CONFIDENCE) {
                continue;
            }

            Map<String, Object> fact =
                    new LinkedHashMap<>();

            fact.put("contentId", contentId);
            fact.put("text", text);
            fact.put("type", type);
            fact.put("confidence", confidence);

            result.add(fact);

            if (result.size() >= 10) {
                break;
            }
        }

        return result;
    }


    private List<String> parseStringList(
            Object rawValue
    ) {
        if (!(rawValue instanceof List<?> values)) {
            return List.of();
        }

        List<String> result =
                new ArrayList<>();

        for (Object raw : values) {
            String value =
                    stringValue(raw).trim();

            if (!value.isBlank()
                    && !result.contains(value)) {
                result.add(value);
            }
        }

        return result;
    }


    private List<ContentActionItemResponse> normalizeActions(
            List<AiActionItemResponse> values,
            boolean mapAllowed,
            boolean compareAllowed,
            boolean calendarAllowed,
            boolean checklistAllowed
    ) {
        if (values == null) {
            return List.of();
        }

        List<ContentActionItemResponse> result =
                new ArrayList<>();

        Set<String> seen =
                new HashSet<>();

        for (AiActionItemResponse item : values) {
            if (item == null) {
                continue;
            }

            String kind =
                    normalizeKind(item.kind());

            if (!ALLOWED_KINDS.contains(kind)) {
                continue;
            }

            if ("MAP_SEARCH".equals(kind)
                    && !mapAllowed) {
                continue;
            }

            if ("COMPARE_SEARCH".equals(kind)
                    && !compareAllowed) {
                continue;
            }

            if ("CALENDAR_ADD".equals(kind)
                    && !calendarAllowed) {
                continue;
            }

            if ("CHECKLIST_CREATE".equals(kind)
                    && !checklistAllowed) {
                continue;
            }

            String title =
                    clean(item.title(), 60);

            String description =
                    clean(item.description(), 180);

            String query =
                    clean(item.query(), 140);

            String eventTitle =
                    clean(item.eventTitle(), 80);

            String eventDate =
                    clean(item.eventDate(), 10);

            List<String> checklistItems =
                    safeItems(
                            item.checklistItems(),
                            8
                    );

            if (title.isBlank()) {
                continue;
            }

            String key;

            if (SEARCH_KINDS.contains(kind)) {
                if (query.isBlank()) {
                    continue;
                }

                key = kind
                        + "|"
                        + query.toLowerCase(Locale.ROOT);

            } else if ("CALENDAR_ADD".equals(kind)) {
                if (eventTitle.isBlank()
                        || !eventDate.matches(
                        "\\d{4}-\\d{2}-\\d{2}"
                )) {
                    continue;
                }

                key = kind
                        + "|"
                        + eventDate
                        + "|"
                        + eventTitle.toLowerCase(Locale.ROOT);

            } else {
                if (checklistItems.size() < 2) {
                    continue;
                }

                key = kind
                        + "|"
                        + String.join(
                        "|",
                        checklistItems.stream()
                                .map(value ->
                                        value.toLowerCase(Locale.ROOT)
                                )
                                .toList()
                );
            }

            if (!seen.add(key)) {
                continue;
            }

            result.add(
                    new ContentActionItemResponse(
                            kind,
                            title,
                            description,
                            query,
                            eventTitle,
                            eventDate,
                            checklistItems
                    )
            );

            if (result.size() >= 3) {
                break;
            }
        }

        return result;
    }


    private ContentActionPlanResponse buildBundleFallback(
            ContentBundleResponse bundle
    ) {
        if (bundle == null
                || bundle.entity() == null
                || bundle.entity().isBlank()) {
            return new ContentActionPlanResponse(
                    "RULE_BASED",
                    List.of()
            );
        }

        String entity =
                clean(bundle.entity(), 100);

        String type =
                normalizeType(bundle.type());

        String focus =
                firstFocus(bundle);

        List<ContentActionItemResponse> actions =
                new ArrayList<>();

        if ("PLACE".equals(type)) {
            actions.add(
                    searchAction(
                            "MAP_SEARCH",
                            "지도에서 찾아보기",
                            "저장 콘텐츠에 반복해서 나온 장소를 네이버지도나 카카오맵에서 검색해요.",
                            entity
                    )
            );

            actions.add(
                    searchAction(
                            "WEB_SEARCH",
                            "최신 정보 찾아보기",
                            "저장된 내용과 함께 볼 최신 정보를 웹에서 검색해요.",
                            joinQuery(entity, focus)
                    )
            );

        } else if ("PRODUCT".equals(type)
                || "BRAND".equals(type)) {

            actions.add(
                    searchAction(
                            "COMPARE_SEARCH",
                            "비교 정보 찾아보기",
                            "저장 콘텐츠의 공통 관심사를 기준으로 비교 정보를 검색해요.",
                            joinQuery(entity, focus, "비교")
                    )
            );

            actions.add(
                    searchAction(
                            "WEB_SEARCH",
                            "관련 정보 더 보기",
                            "이 관심 묶음과 관련된 최신 정보를 웹에서 검색해요.",
                            joinQuery(entity, focus)
                    )
            );

        } else {
            actions.add(
                    searchAction(
                            "WEB_SEARCH",
                            "관련 정보 찾아보기",
                            "저장된 관심 정보와 연결되는 내용을 웹에서 검색해요.",
                            joinQuery(entity, focus)
                    )
            );
        }

        if (actions.size() < 3
                && isChecklistEligible(bundle)
                && bundle.synthesis() != null) {

            List<String> items =
                    safeItems(
                            bundle.synthesis().takeaways(),
                            6
                    );

            if (items.size() >= 2) {
                actions.add(
                        new ContentActionItemResponse(
                                "CHECKLIST_CREATE",
                                "체크리스트 만들기",
                                "저장 콘텐츠의 통합 핵심을 앱 안에서 체크할 수 있게 정리해요.",
                                "",
                                "",
                                "",
                                items
                        )
                );
            }
        }

        return new ContentActionPlanResponse(
                "RULE_BASED",
                actions.stream()
                        .limit(3)
                        .toList()
        );
    }


    private ContentActionPlanResponse buildSingleFallback(
            Content content,
            SingleActionContext context
    ) {
        List<ContentActionItemResponse> actions =
                new ArrayList<>();

        String place =
                bestEntity(
                        context.entityDetails(),
                        Set.of("PLACE")
                );

        String comparable =
                bestEntity(
                        context.entityDetails(),
                        Set.of("PRODUCT", "BRAND")
                );

        if (!place.isBlank()) {
            actions.add(
                    searchAction(
                            "MAP_SEARCH",
                            "지도에서 찾아보기",
                            "이 콘텐츠에서 찾은 장소를 네이버지도나 카카오맵에서 검색해요.",
                            place
                    )
            );
        }

        if (!comparable.isBlank()
                && actions.size() < 3) {
            actions.add(
                    searchAction(
                            "COMPARE_SEARCH",
                            "비교 정보 찾아보기",
                            "이 콘텐츠에서 찾은 상품이나 브랜드의 비교 정보를 검색해요.",
                            joinQuery(
                                    comparable,
                                    firstKeyword(content),
                                    "비교"
                            )
                    )
            );
        }

        if (actions.size() < 3) {
            String searchTarget =
                    !context.primaryEntity().isBlank()
                            ? context.primaryEntity()
                            : safe(content.getTitle());

            actions.add(
                    searchAction(
                            "WEB_SEARCH",
                            "관련 정보 찾아보기",
                            "이 저장 콘텐츠와 관련된 정보를 웹에서 더 찾아봐요.",
                            joinQuery(
                                    searchTarget,
                                    firstKeyword(content)
                            )
                    )
            );
        }

        return new ContentActionPlanResponse(
                "RULE_BASED",
                actions.stream()
                        .limit(3)
                        .toList()
        );
    }


    private String bestEntity(
            List<Map<String, Object>> entities,
            Set<String> allowedTypes
    ) {
        String best = "";
        double bestConfidence = -1.0;

        for (Map<String, Object> entity : entities) {
            String type =
                    normalizeType(
                            stringValue(entity.get("type"))
                    );

            double confidence =
                    numberValue(entity.get("confidence"));

            String name =
                    stringValue(entity.get("name")).trim();

            if (!allowedTypes.contains(type)
                    || confidence < MIN_CONFIDENCE
                    || name.isBlank()) {
                continue;
            }

            if (confidence > bestConfidence) {
                best = name;
                bestConfidence = confidence;
            }
        }

        return best;
    }


    private ContentActionItemResponse searchAction(
            String kind,
            String title,
            String description,
            String query
    ) {
        return new ContentActionItemResponse(
                kind,
                title,
                description,
                query,
                "",
                "",
                List.of()
        );
    }


    private boolean bundleHasPlace(
            ContentBundleResponse bundle
    ) {
        return "PLACE".equals(
                normalizeType(bundle.type())
        );
    }


    private boolean bundleHasComparable(
            ContentBundleResponse bundle
    ) {
        String type =
                normalizeType(bundle.type());

        return "PRODUCT".equals(type)
                || "BRAND".equals(type);
    }


    private boolean hasDateFact(
            ContentBundleResponse bundle
    ) {
        if (bundle.actionFacts() == null) {
            return false;
        }

        return bundle.actionFacts()
                .stream()
                .anyMatch(fact ->
                        fact != null
                                && "DATE_TIME".equals(
                                normalizeType(fact.type())
                        )
                                && fact.confidence() >= MIN_CONFIDENCE
                );
    }


    private boolean isChecklistEligible(
            ContentBundleResponse bundle
    ) {
        if (bundle.contentTypes() != null) {
            boolean typed =
                    bundle.contentTypes()
                            .stream()
                            .map(this::normalizeType)
                            .anyMatch(type ->
                                    "RECIPE".equals(type)
                                            || "HOW_TO".equals(type)
                            );

            if (typed) {
                return true;
            }
        }

        return bundle.categories() != null
                && bundle.categories()
                .stream()
                .anyMatch("음식/레시피"::equals);
    }


    private String firstKeyword(
            Content content
    ) {
        if (content.getKeywords() == null
                || content.getKeywords().isEmpty()) {
            return "";
        }

        return clean(
                content.getKeywords().get(0),
                80
        );
    }


    private String firstFocus(
            ContentBundleResponse bundle
    ) {
        if (bundle.synthesis() != null
                && bundle.synthesis().keyInterests() != null
                && !bundle.synthesis().keyInterests().isEmpty()) {
            return clean(
                    bundle.synthesis().keyInterests().get(0),
                    80
            );
        }

        if (bundle.commonKeywords() != null
                && !bundle.commonKeywords().isEmpty()) {
            return clean(
                    bundle.commonKeywords().get(0),
                    80
            );
        }

        if (bundle.commonTags() != null
                && !bundle.commonTags().isEmpty()) {
            return clean(
                    bundle.commonTags().get(0),
                    80
            );
        }

        return "";
    }


    private List<String> safeItems(
            List<String> values,
            int limit
    ) {
        if (values == null) {
            return List.of();
        }

        return values.stream()
                .filter(value ->
                        value != null
                                && !value.isBlank()
                )
                .map(value ->
                        clean(value, 100)
                )
                .distinct()
                .limit(limit)
                .toList();
    }


    private String joinQuery(
            String... values
    ) {
        List<String> parts =
                new ArrayList<>();

        for (String value : values) {
            String cleaned =
                    clean(value, 100);

            if (!cleaned.isBlank()
                    && !parts.contains(cleaned)) {
                parts.add(cleaned);
            }
        }

        return String.join(" ", parts);
    }


    private String normalizeType(
            String value
    ) {
        return value == null
                ? "OTHER"
                : value.trim().toUpperCase(Locale.ROOT);
    }


    private String normalizeKind(
            String value
    ) {
        return value == null
                ? ""
                : value.trim().toUpperCase(Locale.ROOT);
    }


    private String safe(
            String value
    ) {
        return value == null
                ? ""
                : value.trim();
    }


    private String clean(
            String value,
            int maxLength
    ) {
        if (value == null) {
            return "";
        }

        String cleaned =
                value.trim().replaceAll("\\s+", " ");

        return cleaned.length() <= maxLength
                ? cleaned
                : cleaned.substring(0, maxLength);
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


    private record SingleActionContext(
            String primaryEntity,
            String primaryType,
            String contentType,
            List<String> tags,
            List<Map<String, Object>> entityDetails,
            List<Map<String, Object>> actionFacts,
            boolean hasPlace,
            boolean hasComparable,
            boolean hasDateFact,
            boolean checklistEligible
    ) {
    }
}
