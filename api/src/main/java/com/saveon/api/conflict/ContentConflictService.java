package com.saveon.api.conflict;

import com.saveon.api.conflict.agent.ConflictAgentEvidence;
import com.saveon.api.conflict.agent.ConflictAgentItem;
import com.saveon.api.conflict.agent.ConflictAgentResponse;
import com.saveon.api.conflict.agent.ContentConflictAgentClient;
import com.saveon.api.conflict.dto.ContentConflictEvidenceResponse;
import com.saveon.api.conflict.dto.ContentConflictResponse;
import com.saveon.api.content.Content;
import com.saveon.api.content.ContentService;
import com.saveon.api.content.ContentStatus;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Service
public class ContentConflictService {

    private static final int DEFAULT_LIMIT = 6;
    private static final int MAX_LIMIT = 12;
    private static final int MAX_AGENT_CLAIMS = 40;

    private static final Set<String> SUPPORTED_TYPES = Set.of(
            "DATE_TIME",
            "PRICE",
            "LOCATION",
            "STATISTIC",
            "PRODUCT_PERFORMANCE",
            "HEALTH_BEAUTY",
            "TRAVEL_RULE",
            "OTHER"
    );

    private static final Pattern DATE_PATTERN = Pattern.compile(
            "(?:(\\d{4})[./년\\-]\\s*)?"
                    + "(\\d{1,2})[./월\\-]\\s*"
                    + "(\\d{1,2})(?:일)?"
    );

    private static final Pattern KOREAN_DATE_PATTERN = Pattern.compile(
            "(\\d{1,2})월\\s*(\\d{1,2})일"
    );

    private static final Pattern PRICE_PATTERN = Pattern.compile(
            "(?:₩\\s*)?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})\\s*원?"
    );

    private static final Pattern PERCENT_PATTERN = Pattern.compile(
            "([0-9]+(?:\\.[0-9]+)?)\\s*%"
    );

    private final ContentService contentService;
    private final ContentConflictAgentClient agentClient;
    private final JsonMapper jsonMapper;

    public ContentConflictService(
            ContentService contentService,
            ContentConflictAgentClient agentClient
    ) {
        this.contentService = contentService;
        this.agentClient = agentClient;
        this.jsonMapper = JsonMapper.builder().build();
    }

    public List<ContentConflictResponse> findConflicts(
            Integer requestedLimit
    ) {
        int limit =
                requestedLimit != null
                        ? requestedLimit
                        : DEFAULT_LIMIT;

        limit = Math.max(1, Math.min(limit, MAX_LIMIT));

        List<ContentClaim> allClaims =
                contentService.findAll().stream()
                        .filter(content ->
                                content.getStatus()
                                        == ContentStatus.COMPLETED
                        )
                        .flatMap(content ->
                                claimsFor(content).stream()
                        )
                        .toList();

        if (allClaims.size() < 2) {
            return List.of();
        }

        List<ContentClaim> candidates =
                buildCandidateClaims(allClaims);

        if (candidates.size() < 2) {
            return List.of();
        }

        List<ContentConflictResponse> agentConflicts =
                detectWithAgent(candidates);

        List<ContentConflictResponse> deterministic =
                detectDeterministic(candidates);

        LinkedHashMap<String, ContentConflictResponse> merged =
                new LinkedHashMap<>();

        for (ContentConflictResponse item : agentConflicts) {
            merged.put(signature(item), item);
        }

        for (ContentConflictResponse item : deterministic) {
            merged.putIfAbsent(signature(item), item);
        }

        return merged.values().stream()
                .limit(limit)
                .toList();
    }

    private List<ContentClaim> buildCandidateClaims(
            List<ContentClaim> claims
    ) {
        Set<ClaimKey> acceptedKeys =
                new LinkedHashSet<>();

        for (int left = 0; left < claims.size(); left++) {
            for (int right = left + 1; right < claims.size(); right++) {
                ContentClaim a = claims.get(left);
                ContentClaim b = claims.get(right);

                if (a.contentId().equals(b.contentId())) {
                    continue;
                }

                if (!a.claimType().equals(b.claimType())) {
                    continue;
                }

                Set<String> sharedSubjects =
                        new HashSet<>(a.subjects());
                sharedSubjects.retainAll(b.subjects());

                if (sharedSubjects.isEmpty()) {
                    continue;
                }

                if (normalizeText(a.claimText())
                        .equals(normalizeText(b.claimText()))) {
                    continue;
                }

                String subject =
                        sharedSubjects.iterator().next();

                acceptedKeys.add(
                        new ClaimKey(
                                a.contentId(),
                                a.claimType(),
                                subject
                        )
                );
                acceptedKeys.add(
                        new ClaimKey(
                                b.contentId(),
                                b.claimType(),
                                subject
                        )
                );
            }
        }

        List<ContentClaim> result =
                new ArrayList<>();

        for (ClaimKey key : acceptedKeys) {
            claims.stream()
                    .filter(claim ->
                            claim.contentId().equals(key.contentId())
                                    && claim.claimType()
                                    .equals(key.claimType())
                                    && claim.subjects()
                                    .contains(key.subject())
                    )
                    .findFirst()
                    .ifPresent(claim ->
                            result.add(
                                    claim.withPrimarySubject(
                                            key.subject()
                                    )
                            )
                    );

            if (result.size() >= MAX_AGENT_CLAIMS) {
                break;
            }
        }

        return result;
    }

    private List<ContentConflictResponse> detectWithAgent(
            List<ContentClaim> candidates
    ) {
        try {
            List<Map<String, Object>> payload =
                    candidates.stream()
                            .limit(MAX_AGENT_CLAIMS)
                            .map(this::toAgentPayload)
                            .toList();

            ConflictAgentResponse response =
                    agentClient.detect(payload);

            if (response == null
                    || response.conflicts() == null) {
                return List.of();
            }

            Map<Long, ContentClaim> byId =
                    candidates.stream()
                            .collect(Collectors.toMap(
                                    ContentClaim::contentId,
                                    value -> value,
                                    (first, ignored) -> first
                            ));

            List<ContentConflictResponse> result =
                    new ArrayList<>();

            for (ConflictAgentItem item :
                    response.conflicts()) {

                if (item == null
                        || item.evidences() == null
                        || item.evidences().size() < 2) {
                    continue;
                }

                List<ContentConflictEvidenceResponse> evidences =
                        new ArrayList<>();

                for (ConflictAgentEvidence evidence :
                        item.evidences()) {
                    ContentClaim source =
                            byId.get(evidence.contentId());

                    if (source == null) {
                        continue;
                    }

                    evidences.add(
                            new ContentConflictEvidenceResponse(
                                    source.contentId(),
                                    source.title(),
                                    nonBlank(
                                            evidence.claimText(),
                                            source.claimText()
                                    ),
                                    evidence.value() != null
                                            ? evidence.value()
                                            : ""
                            )
                    );
                }

                if (evidences.size() < 2) {
                    continue;
                }

                result.add(
                        new ContentConflictResponse(
                                stableKey(
                                        item.subject(),
                                        item.claimType(),
                                        evidences
                                ),
                                nonBlank(
                                        item.subject(),
                                        candidates.get(0)
                                                .primarySubject()
                                ),
                                nonBlank(
                                        item.claimType(),
                                        "OTHER"
                                ),
                                nonBlank(
                                        item.title(),
                                        "저장한 정보가 서로 달라요"
                                ),
                                nonBlank(
                                        item.description(),
                                        "같은 주제의 저장물에서 서로 다른 정보가 확인됐어요."
                                ),
                                "ERROR".equalsIgnoreCase(
                                        item.severity()
                                )
                                        ? "ERROR"
                                        : "WARN",
                                evidences,
                                "AGENT"
                        )
                );
            }

            return result;

        } catch (Exception error) {
            System.err.println(
                    "⚠️ 저장물 상충 Agent 실패 - 규칙 기반 탐지로 계속: "
                            + error.getMessage()
            );

            return List.of();
        }
    }

    private List<ContentConflictResponse> detectDeterministic(
            List<ContentClaim> candidates
    ) {
        List<ContentConflictResponse> result =
                new ArrayList<>();
        Set<String> seen =
                new HashSet<>();

        for (int left = 0; left < candidates.size(); left++) {
            for (int right = left + 1;
                 right < candidates.size();
                 right++) {

                ContentClaim a = candidates.get(left);
                ContentClaim b = candidates.get(right);

                if (a.contentId().equals(b.contentId())
                        || !a.claimType().equals(b.claimType())
                        || !a.primarySubject()
                        .equals(b.primarySubject())) {
                    continue;
                }

                String valueA =
                        explicitValue(
                                a.claimType(),
                                a.claimText()
                        );
                String valueB =
                        explicitValue(
                                b.claimType(),
                                b.claimText()
                        );

                if (valueA.isBlank()
                        || valueB.isBlank()
                        || valueA.equals(valueB)) {
                    continue;
                }

                String pairKey =
                        a.primarySubject()
                                + "|"
                                + a.claimType()
                                + "|"
                                + Math.min(
                                        a.contentId(),
                                        b.contentId()
                                )
                                + "|"
                                + Math.max(
                                        a.contentId(),
                                        b.contentId()
                                );

                if (!seen.add(pairKey)) {
                    continue;
                }

                List<ContentConflictEvidenceResponse> evidences =
                        List.of(
                                new ContentConflictEvidenceResponse(
                                        a.contentId(),
                                        a.title(),
                                        a.claimText(),
                                        valueA
                                ),
                                new ContentConflictEvidenceResponse(
                                        b.contentId(),
                                        b.title(),
                                        b.claimText(),
                                        valueB
                                )
                        );

                result.add(
                        new ContentConflictResponse(
                                stableKey(
                                        a.primarySubject(),
                                        a.claimType(),
                                        evidences
                                ),
                                a.primarySubject(),
                                a.claimType(),
                                fallbackTitle(
                                        a.primarySubject(),
                                        a.claimType()
                                ),
                                "같은 주제의 저장물에 "
                                        + valueA
                                        + "와 "
                                        + valueB
                                        + "처럼 서로 다른 값이 적혀 있어요.",
                                "WARN",
                                evidences,
                                "RULE_BASED"
                        )
                );
            }
        }

        return result;
    }

    private List<ContentClaim> claimsFor(
            Content content
    ) {
        Map<String, Object> structured =
                parseStructured(
                        content.getStructuredAnalysis()
                );

        List<String> subjects =
                entitySubjects(
                        content,
                        structured
                );

        if (subjects.isEmpty()) {
            return List.of();
        }

        String verificationStatus =
                stringValue(
                        structured.get(
                                "verificationStatus"
                        )
                );

        List<Map<String, Object>> factChecks =
                mapList(
                        structured.get("factChecks")
                );

        List<Map<String, Object>> claims =
                mapList(
                        structured.get("claims")
                );

        List<ContentClaim> result =
                new ArrayList<>();

        for (Map<String, Object> claim : claims) {
            String text =
                    stringValue(claim.get("text"));
            String type =
                    stringValue(claim.get("type"))
                            .toUpperCase(Locale.ROOT);

            if (text.isBlank()
                    || type.isBlank()
                    || !SUPPORTED_TYPES.contains(type)) {
                continue;
            }

            Object verifiable =
                    claim.get("verifiable");

            if (verifiable instanceof Boolean flag
                    && !flag) {
                continue;
            }

            result.add(
                    new ContentClaim(
                            content.getId(),
                            safe(content.getTitle()),
                            text,
                            type,
                            subjects,
                            subjects.get(0),
                            verificationStatus,
                            relatedFactChecks(
                                    text,
                                    factChecks
                            )
                    )
            );
        }

        return result;
    }

    private List<String> entitySubjects(
            Content content,
            Map<String, Object> structured
    ) {
        LinkedHashSet<String> result =
                new LinkedHashSet<>();

        Object details =
                structured.get("entityDetails");

        if (details instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    Object name =
                            map.get("name");

                    if (name != null) {
                        String normalized =
                                normalizeSubject(
                                        String.valueOf(name)
                                );

                        if (!normalized.isBlank()) {
                            result.add(normalized);
                        }
                    }
                }
            }
        }

        if (content.getEntities() != null) {
            for (String entity :
                    content.getEntities()) {
                String normalized =
                        normalizeSubject(entity);

                if (!normalized.isBlank()) {
                    result.add(normalized);
                }
            }
        }

        return new ArrayList<>(result);
    }

    private List<Map<String, Object>> relatedFactChecks(
            String claimText,
            List<Map<String, Object>> factChecks
    ) {
        String normalizedClaim =
                normalizeText(claimText);

        return factChecks.stream()
                .filter(check -> {
                    String candidate =
                            stringValue(
                                    check.get("claim")
                            );

                    if (candidate.isBlank()) {
                        candidate =
                                stringValue(
                                        check.get("claimText")
                                );
                    }

                    String normalized =
                            normalizeText(candidate);

                    return normalized.isBlank()
                            || normalizedClaim.contains(normalized)
                            || normalized.contains(normalizedClaim);
                })
                .limit(3)
                .toList();
    }

    private Map<String, Object> toAgentPayload(
            ContentClaim claim
    ) {
        Map<String, Object> result =
                new LinkedHashMap<>();

        result.put(
                "contentId",
                claim.contentId()
        );
        result.put(
                "title",
                claim.title()
        );
        result.put(
                "subject",
                claim.primarySubject()
        );
        result.put(
                "claimType",
                claim.claimType()
        );
        result.put(
                "claimText",
                claim.claimText()
        );
        result.put(
                "verificationStatus",
                claim.verificationStatus()
        );
        result.put(
                "factChecks",
                claim.factChecks()
        );

        return result;
    }

    private String explicitValue(
            String claimType,
            String text
    ) {
        return switch (claimType) {
            case "DATE_TIME" ->
                    extractDate(text);
            case "PRICE" ->
                    extractPrice(text);
            case "STATISTIC" ->
                    extractPercent(text);
            default -> "";
        };
    }

    private String extractDate(
            String text
    ) {
        Matcher matcher =
                KOREAN_DATE_PATTERN.matcher(text);

        if (matcher.find()) {
            return twoDigits(matcher.group(1))
                    + "-"
                    + twoDigits(matcher.group(2));
        }

        matcher =
                DATE_PATTERN.matcher(text);

        if (matcher.find()) {
            String year =
                    matcher.group(1);

            String prefix =
                    year != null
                            ? year + "-"
                            : "";

            return prefix
                    + twoDigits(matcher.group(2))
                    + "-"
                    + twoDigits(matcher.group(3));
        }

        return "";
    }

    private String extractPrice(
            String text
    ) {
        Matcher matcher =
                PRICE_PATTERN.matcher(text);

        if (!matcher.find()) {
            return "";
        }

        String digits =
                matcher.group(1)
                        .replace(",", "");

        try {
            long value =
                    Long.parseLong(digits);

            if (value < 1000) {
                return "";
            }

            return String.format(
                    "%,d원",
                    value
            );
        } catch (NumberFormatException ignored) {
            return "";
        }
    }

    private String extractPercent(
            String text
    ) {
        Matcher matcher =
                PERCENT_PATTERN.matcher(text);

        return matcher.find()
                ? matcher.group(1) + "%"
                : "";
    }

    private String fallbackTitle(
            String subject,
            String claimType
    ) {
        String label =
                switch (claimType) {
                    case "DATE_TIME" -> "날짜 정보";
                    case "PRICE" -> "가격 정보";
                    case "STATISTIC" -> "수치 정보";
                    default -> "정보";
                };

        return subject
                + "의 "
                + label
                + "가 서로 달라요";
    }

    private String signature(
            ContentConflictResponse response
    ) {
        String ids =
                response.evidences().stream()
                        .map(value ->
                                String.valueOf(
                                        value.contentId()
                                )
                        )
                        .sorted()
                        .collect(Collectors.joining(","));

        return normalizeSubject(
                response.subject()
        )
                + "|"
                + response.claimType()
                + "|"
                + ids;
    }

    private String stableKey(
            String subject,
            String claimType,
            List<ContentConflictEvidenceResponse> evidences
    ) {
        String raw =
                normalizeSubject(subject)
                        + "|"
                        + claimType
                        + "|"
                        + evidences.stream()
                        .map(value ->
                                String.valueOf(
                                        value.contentId()
                                )
                        )
                        .sorted()
                        .collect(Collectors.joining(","));

        try {
            MessageDigest digest =
                    MessageDigest.getInstance(
                            "SHA-256"
                    );

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
                    Math.abs(raw.hashCode())
            );
        }
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

            return parsed;

        } catch (Exception ignored) {
            return Map.of();
        }
    }

    private List<Map<String, Object>> mapList(
            Object value
    ) {
        if (!(value instanceof List<?> list)) {
            return List.of();
        }

        List<Map<String, Object>> result =
                new ArrayList<>();

        for (Object item : list) {
            if (item instanceof Map<?, ?> raw) {
                Map<String, Object> converted =
                        new HashMap<>();

                for (Map.Entry<?, ?> entry :
                        raw.entrySet()) {
                    if (entry.getKey() != null) {
                        converted.put(
                                String.valueOf(
                                        entry.getKey()
                                ),
                                entry.getValue()
                        );
                    }
                }

                result.add(converted);
            }
        }

        return result;
    }

    private String normalizeSubject(
            String value
    ) {
        return safe(value)
                .replaceAll("[#]+", "")
                .replaceAll("\\s+", " ")
                .trim()
                .toLowerCase(Locale.ROOT);
    }

    private String normalizeText(
            String value
    ) {
        return safe(value)
                .replaceAll("\\s+", "")
                .replaceAll("[,.!?~]", "")
                .toLowerCase(Locale.ROOT);
    }

    private String stringValue(
            Object value
    ) {
        return value != null
                ? String.valueOf(value).trim()
                : "";
    }

    private String nonBlank(
            String value,
            String fallback
    ) {
        return value != null
                && !value.isBlank()
                ? value.trim()
                : fallback;
    }

    private String twoDigits(
            String value
    ) {
        try {
            return String.format(
                    "%02d",
                    Integer.parseInt(value)
            );
        } catch (NumberFormatException ignored) {
            return value;
        }
    }

    private String safe(
            String value
    ) {
        return value != null ? value : "";
    }

    private record ClaimKey(
            Long contentId,
            String claimType,
            String subject
    ) {
    }

    private record ContentClaim(
            Long contentId,
            String title,
            String claimText,
            String claimType,
            List<String> subjects,
            String primarySubject,
            String verificationStatus,
            List<Map<String, Object>> factChecks
    ) {
        ContentClaim withPrimarySubject(
                String value
        ) {
            return new ContentClaim(
                    contentId,
                    title,
                    claimText,
                    claimType,
                    subjects,
                    value,
                    verificationStatus,
                    factChecks
            );
        }
    }
}
