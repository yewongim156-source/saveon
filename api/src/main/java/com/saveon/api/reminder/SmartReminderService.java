package com.saveon.api.reminder;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import com.saveon.api.content.Content;
import com.saveon.api.content.ContentRepository;
import com.saveon.api.content.ContentStatus;
import com.saveon.api.reminder.dto.SmartReminderResponse;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
public class SmartReminderService {

    private static final int LOOKBACK_DAYS = 30;

    private static final Set<String> EVENT_WORDS = Set.of(
            "세일", "할인", "쿠폰", "블랙프라이데이", "블프",
            "행사", "이벤트", "팝업", "오픈", "마감", "선착순"
    );

    private static final Set<String> TRAVEL_WORDS = Set.of(
            "여행", "숙소", "호텔", "항공", "공항", "맛집", "카페",
            "웨이팅", "관광", "코스", "핫플", "나들이"
    );

    private final ContentRepository contentRepository;
    private final ObjectMapper objectMapper;

    public SmartReminderService(
            ContentRepository contentRepository,
            ObjectMapper objectMapper
    ) {
        this.contentRepository = contentRepository;
        this.objectMapper = objectMapper;
    }

    public List<SmartReminderResponse> getReminders(int limit) {
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime lookback = now.minusDays(LOOKBACK_DAYS);

        List<Content> completed = contentRepository.findAll().stream()
                .filter(content -> content.getStatus() == ContentStatus.COMPLETED)
                .filter(content -> content.getCreatedAt() != null)
                .filter(content -> !content.getCreatedAt().isBefore(lookback))
                .sorted(Comparator.comparing(Content::getCreatedAt).reversed())
                .toList();

        Map<String, Integer> repeatedKeywords = countRepeated(completed, ValueKind.KEYWORD);
        Map<String, Integer> repeatedEntities = countRepeated(completed, ValueKind.ENTITY);

        List<SmartReminderResponse> candidates = new ArrayList<>();

        for (Content content : completed) {
            SmartReminderResponse reminder = buildReminder(
                    content,
                    now,
                    repeatedKeywords,
                    repeatedEntities
            );

            if (reminder != null) {
                candidates.add(reminder);
            }
        }

        Map<String, SmartReminderResponse> deduplicated = new LinkedHashMap<>();
        candidates.stream()
                .sorted(
                        Comparator.comparingInt(SmartReminderResponse::score)
                                .reversed()
                                .thenComparing(
                                        reminder -> contentCreatedAt(reminder.contentId(), completed),
                                        Comparator.reverseOrder()
                                )
                )
                .forEach(reminder -> deduplicated.putIfAbsent(
                        reminder.key(),
                        reminder
                ));

        return deduplicated.values().stream()
                .limit(limit)
                .toList();
    }

    private SmartReminderResponse buildReminder(
            Content content,
            LocalDateTime now,
            Map<String, Integer> repeatedKeywords,
            Map<String, Integer> repeatedEntities
    ) {
        String searchable = searchableText(content);
        List<String> evidence = new ArrayList<>();
        int score = 0;
        String type = "REVISIT";
        String badge = "다시 보기";
        String title;
        String description;

        String dateClaim = findDateClaim(content);
        if (dateClaim != null) {
            score += 6;
            type = "DATE_CHECK";
            badge = "날짜 확인";
            evidence.add(dateClaim);
        }

        String eventWord = firstContained(searchable, EVENT_WORDS);
        if (eventWord != null) {
            score += 4;
            if (!"DATE_CHECK".equals(type)) {
                type = "EVENT_CHECK";
                badge = "놓치기 전에";
            }
            evidence.add("행사·혜택 관련 표현: " + eventWord);
        }

        boolean travel = containsCategory(content, "장소/여행")
                || firstContained(searchable, TRAVEL_WORDS) != null;
        if (travel) {
            score += 3;
            if ("REVISIT".equals(type)) {
                type = "TRAVEL_REVISIT";
                badge = "외출 전에";
            }
            evidence.add("장소·여행 관련 저장물");
        }

        String repeated = strongestRepeatedInterest(
                content,
                repeatedKeywords,
                repeatedEntities
        );
        if (repeated != null) {
            score += 3;
            evidence.add("최근 반복 저장: " + repeated);
        }

        long ageDays = Math.max(
                0,
                Duration.between(content.getCreatedAt(), now).toDays()
        );
        if (ageDays >= 2) {
            score += Math.min(3, (int) ageDays / 3 + 1);
        }

        // 날짜/행사/여행/반복 관심 중 하나라도 있어야 노출한다.
        if (score < 3) {
            return null;
        }

        String subject = content.getTitle() != null && !content.getTitle().isBlank()
                ? content.getTitle().trim()
                : "저장한 콘텐츠";

        switch (type) {
            case "DATE_CHECK" -> {
                title = "날짜가 있는 저장물, 한 번 더 확인할까요?";
                description = trimForCard(subject) + "의 일정 정보를 놓치지 않게 다시 확인해보세요.";
            }
            case "EVENT_CHECK" -> {
                title = "혜택이나 행사가 끝나기 전에 다시 볼까요?";
                description = trimForCard(subject) + "에 세일·이벤트 관련 정보가 있어요.";
            }
            case "TRAVEL_REVISIT" -> {
                title = "외출이나 여행 전에 다시 보기 좋아요";
                description = trimForCard(subject) + "처럼 장소·여행 관련 저장물을 다시 확인해보세요.";
            }
            default -> {
                title = "최근 관심사라 다시 보기 추천해요";
                description = repeated != null
                        ? repeated + " 관련 저장이 반복되고 있어요. 이전 저장물도 함께 다시 확인해보세요."
                        : trimForCard(subject) + "을 다시 확인해볼 만한 시점이에요.";
            }
        }

        return new SmartReminderResponse(
                type + ":" + content.getId(),
                type,
                title,
                description,
                badge,
                content.getId(),
                subject,
                content.getSourceUrl(),
                evidence.stream().distinct().limit(3).toList(),
                score
        );
    }

    private String findDateClaim(Content content) {
        String structured = content.getStructuredAnalysis();
        if (structured == null || structured.isBlank()) {
            return null;
        }

        try {
            JsonNode root = objectMapper.readTree(structured);
            JsonNode claims = root.path("claims");
            if (!claims.isArray()) {
                return null;
            }

            for (JsonNode claim : claims) {
                if (!"DATE_TIME".equalsIgnoreCase(claim.path("type").asText())) {
                    continue;
                }

                String text = claim.path("text").asText("").trim();
                if (!text.isBlank()) {
                    return "날짜·시간 근거: " + text;
                }
            }
        } catch (Exception ignored) {
            // Reminder는 보조 기능이므로 structured JSON 오류가 전체 조회를 막지 않는다.
        }

        return null;
    }

    private Map<String, Integer> countRepeated(
            List<Content> contents,
            ValueKind kind
    ) {
        Map<String, Integer> counts = new HashMap<>();

        for (Content content : contents) {
            List<String> values = kind == ValueKind.KEYWORD
                    ? content.getKeywords()
                    : content.getEntities();

            if (values == null) {
                continue;
            }

            values.stream()
                    .filter(value -> value != null && !value.isBlank())
                    .map(String::trim)
                    .map(this::normalize)
                    .filter(value -> value.length() >= 2)
                    .distinct()
                    .forEach(value -> counts.merge(value, 1, Integer::sum));
        }

        counts.entrySet().removeIf(entry -> entry.getValue() < 2);
        return counts;
    }

    private String strongestRepeatedInterest(
            Content content,
            Map<String, Integer> repeatedKeywords,
            Map<String, Integer> repeatedEntities
    ) {
        String bestLabel = null;
        int bestCount = 0;

        if (content.getKeywords() != null) {
            for (String keyword : content.getKeywords()) {
                if (keyword == null || keyword.isBlank()) {
                    continue;
                }
                int count = repeatedKeywords.getOrDefault(normalize(keyword), 0);
                if (count > bestCount) {
                    bestLabel = keyword.trim();
                    bestCount = count;
                }
            }
        }

        if (content.getEntities() != null) {
            for (String entity : content.getEntities()) {
                if (entity == null || entity.isBlank()) {
                    continue;
                }
                int count = repeatedEntities.getOrDefault(normalize(entity), 0);
                if (count > bestCount) {
                    bestLabel = entity.trim();
                    bestCount = count;
                }
            }
        }

        return bestCount >= 2 ? bestLabel : null;
    }

    private boolean containsCategory(Content content, String category) {
        return content.getCategories() != null
                && content.getCategories().stream()
                .anyMatch(value -> category.equalsIgnoreCase(value));
    }

    private String searchableText(Content content) {
        List<String> parts = new ArrayList<>();
        add(parts, content.getTitle());
        add(parts, content.getSummary());

        if (content.getCategories() != null) {
            parts.addAll(content.getCategories());
        }
        if (content.getKeywords() != null) {
            parts.addAll(content.getKeywords());
        }
        if (content.getEntities() != null) {
            parts.addAll(content.getEntities());
        }

        return String.join(" ", parts).toLowerCase(Locale.ROOT);
    }

    private void add(List<String> parts, String value) {
        if (value != null && !value.isBlank()) {
            parts.add(value);
        }
    }

    private String firstContained(String text, Set<String> candidates) {
        return candidates.stream()
                .filter(text::contains)
                .findFirst()
                .orElse(null);
    }

    private String normalize(String value) {
        return value == null
                ? ""
                : value.trim().toLowerCase(Locale.ROOT)
                .replaceAll("\\s+", " ");
    }

    private String trimForCard(String value) {
        if (value.length() <= 34) {
            return value;
        }
        return value.substring(0, 34) + "…";
    }

    private LocalDateTime contentCreatedAt(
            Long contentId,
            List<Content> contents
    ) {
        return contents.stream()
                .filter(content -> content.getId().equals(contentId))
                .map(Content::getCreatedAt)
                .findFirst()
                .orElse(LocalDateTime.MIN);
    }

    private enum ValueKind {
        KEYWORD,
        ENTITY
    }
}
