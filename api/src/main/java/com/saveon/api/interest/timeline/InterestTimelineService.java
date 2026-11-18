package com.saveon.api.interest.timeline;

import com.saveon.api.content.Content;
import com.saveon.api.content.ContentRepository;
import com.saveon.api.content.ContentStatus;
import com.saveon.api.interest.timeline.dto.InterestTimelineResponse;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class InterestTimelineService {

    private static final int RECENT_DAYS = 7;
    private static final int LONG_WINDOW_DAYS = 30;

    private final ContentRepository contentRepository;

    public InterestTimelineService(ContentRepository contentRepository) {
        this.contentRepository = contentRepository;
    }

    public InterestTimelineResponse getTimeline() {
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime recentStart = now.minusDays(RECENT_DAYS);
        LocalDateTime previousStart = now.minusDays(RECENT_DAYS * 2L);
        LocalDateTime longWindowStart = now.minusDays(LONG_WINDOW_DAYS);

        List<Content> completed = contentRepository.findAll().stream()
                .filter(content -> content.getStatus() == ContentStatus.COMPLETED)
                .filter(content -> content.getCreatedAt() != null)
                .toList();

        List<Content> recent = completed.stream()
                .filter(content -> !content.getCreatedAt().isBefore(recentStart))
                .toList();

        List<Content> previous = completed.stream()
                .filter(content -> !content.getCreatedAt().isBefore(previousStart))
                .filter(content -> content.getCreatedAt().isBefore(recentStart))
                .toList();

        List<Content> last30Days = completed.stream()
                .filter(content -> !content.getCreatedAt().isBefore(longWindowStart))
                .toList();

        Map<String, Integer> recentCategories = countValues(recent, ValueKind.CATEGORY);
        Map<String, Integer> previousCategories = countValues(previous, ValueKind.CATEGORY);

        List<InterestTimelineResponse.TrendItem> categoryTrends = buildCategoryTrends(
                recentCategories,
                previousCategories
        );

        Map<String, Integer> recentKeywords = countValues(recent, ValueKind.KEYWORD);
        Map<String, Integer> previousKeywords = countValues(previous, ValueKind.KEYWORD);
        Map<String, Integer> recentEntities = countValues(recent, ValueKind.ENTITY);
        Map<String, Integer> previousEntities = countValues(previous, ValueKind.ENTITY);

        List<InterestTimelineResponse.InterestItem> emerging = buildEmergingInterests(
                recentKeywords,
                previousKeywords,
                recentEntities,
                previousEntities
        );

        List<InterestTimelineResponse.InterestItem> topInterests = buildTopInterests(last30Days);

        return new InterestTimelineResponse(
                RECENT_DAYS,
                recent.size(),
                previous.size(),
                last30Days.size(),
                buildSummary(recent.size(), previous.size(), categoryTrends, emerging),
                categoryTrends,
                emerging,
                topInterests
        );
    }

    private List<InterestTimelineResponse.TrendItem> buildCategoryTrends(
            Map<String, Integer> recent,
            Map<String, Integer> previous
    ) {
        Map<String, String> labels = new LinkedHashMap<>();
        recent.keySet().forEach(key -> labels.putIfAbsent(key, key));
        previous.keySet().forEach(key -> labels.putIfAbsent(key, key));

        return labels.keySet().stream()
                .map(label -> {
                    int currentCount = recent.getOrDefault(label, 0);
                    int previousCount = previous.getOrDefault(label, 0);
                    int delta = currentCount - previousCount;
                    String direction = delta > 0
                            ? (previousCount == 0 ? "NEW" : "UP")
                            : delta < 0 ? "DOWN" : "STEADY";

                    return new InterestTimelineResponse.TrendItem(
                            label,
                            currentCount,
                            previousCount,
                            delta,
                            direction
                    );
                })
                .filter(item -> item.currentCount() + item.previousCount() >= 2)
                .sorted(
                        Comparator
                                .comparingInt((InterestTimelineResponse.TrendItem item) -> Math.abs(item.delta()))
                                .reversed()
                                .thenComparing(
                                        Comparator.comparingInt(InterestTimelineResponse.TrendItem::currentCount)
                                                .reversed()
                                )
                )
                .limit(5)
                .toList();
    }

    private List<InterestTimelineResponse.InterestItem> buildEmergingInterests(
            Map<String, Integer> recentKeywords,
            Map<String, Integer> previousKeywords,
            Map<String, Integer> recentEntities,
            Map<String, Integer> previousEntities
    ) {
        List<InterestTimelineResponse.InterestItem> candidates = new ArrayList<>();

        recentKeywords.forEach((label, count) -> {
            if (count >= 2 && previousKeywords.getOrDefault(label, 0) == 0) {
                candidates.add(new InterestTimelineResponse.InterestItem(
                        label,
                        "KEYWORD",
                        count
                ));
            }
        });

        recentEntities.forEach((label, count) -> {
            if (count >= 2 && previousEntities.getOrDefault(label, 0) == 0) {
                candidates.add(new InterestTimelineResponse.InterestItem(
                        label,
                        "ENTITY",
                        count
                ));
            }
        });

        return candidates.stream()
                .sorted(
                        Comparator
                                .comparingInt(InterestTimelineResponse.InterestItem::count)
                                .reversed()
                                .thenComparing(InterestTimelineResponse.InterestItem::label)
                )
                .limit(5)
                .toList();
    }

    private List<InterestTimelineResponse.InterestItem> buildTopInterests(
            List<Content> contents
    ) {
        Map<String, Integer> keywords = countValues(contents, ValueKind.KEYWORD);
        Map<String, Integer> entities = countValues(contents, ValueKind.ENTITY);

        List<InterestTimelineResponse.InterestItem> combined = new ArrayList<>();
        keywords.forEach((label, count) -> {
            if (count >= 2) {
                combined.add(new InterestTimelineResponse.InterestItem(label, "KEYWORD", count));
            }
        });
        entities.forEach((label, count) -> {
            if (count >= 2) {
                combined.add(new InterestTimelineResponse.InterestItem(label, "ENTITY", count));
            }
        });

        Map<String, InterestTimelineResponse.InterestItem> deduplicated = new LinkedHashMap<>();
        combined.stream()
                .sorted(
                        Comparator
                                .comparingInt(InterestTimelineResponse.InterestItem::count)
                                .reversed()
                )
                .forEach(item -> deduplicated.putIfAbsent(
                        normalize(item.label()),
                        item
                ));

        return deduplicated.values().stream()
                .limit(8)
                .toList();
    }

    private Map<String, Integer> countValues(
            List<Content> contents,
            ValueKind kind
    ) {
        Map<String, Integer> counts = new HashMap<>();
        Map<String, String> canonicalLabels = new HashMap<>();

        for (Content content : contents) {
            List<String> values = switch (kind) {
                case CATEGORY -> content.getCategories();
                case KEYWORD -> content.getKeywords();
                case ENTITY -> content.getEntities();
            };

            if (values == null) {
                continue;
            }

            values.stream()
                    .filter(value -> value != null && !value.isBlank())
                    .map(String::trim)
                    .distinct()
                    .forEach(value -> {
                        String normalized = normalize(value);
                        if (normalized.isBlank() || isNoise(value, kind)) {
                            return;
                        }
                        canonicalLabels.putIfAbsent(normalized, value);
                        counts.merge(normalized, 1, Integer::sum);
                    });
        }

        Map<String, Integer> labeledCounts = new LinkedHashMap<>();
        counts.entrySet().stream()
                .sorted(Map.Entry.<String, Integer>comparingByValue().reversed())
                .forEach(entry -> labeledCounts.put(
                        canonicalLabels.getOrDefault(entry.getKey(), entry.getKey()),
                        entry.getValue()
                ));
        return labeledCounts;
    }

    private String buildSummary(
            int recentCount,
            int previousCount,
            List<InterestTimelineResponse.TrendItem> trends,
            List<InterestTimelineResponse.InterestItem> emerging
    ) {
        if (recentCount == 0) {
            return "최근 7일간 새로 저장한 콘텐츠가 아직 없어요.";
        }

        InterestTimelineResponse.TrendItem strongestUp = trends.stream()
                .filter(item -> item.delta() > 0)
                .findFirst()
                .orElse(null);

        if (strongestUp != null) {
            if (strongestUp.direction().equals("NEW")) {
                return "최근에는 " + strongestUp.label() + " 관련 저장이 새롭게 늘고 있어요.";
            }
            return "최근에는 " + strongestUp.label() + " 관련 저장이 이전 7일보다 늘었어요.";
        }

        if (!emerging.isEmpty()) {
            return "최근 저장에서 ‘" + emerging.getFirst().label() + "’ 관심사가 새롭게 반복되고 있어요.";
        }

        if (recentCount > previousCount) {
            return "최근 7일간 저장 활동이 이전 7일보다 활발해졌어요.";
        }

        if (recentCount < previousCount) {
            return "최근 7일간 저장 수는 줄었지만, 관심 주제는 계속 추적하고 있어요.";
        }

        return "최근 7일간 관심 흐름이 비교적 비슷하게 이어지고 있어요.";
    }

    private String normalize(String value) {
        return value
                .trim()
                .toLowerCase(Locale.ROOT)
                .replaceAll("\\s+", " ");
    }

    private boolean isNoise(String value, ValueKind kind) {
        String normalized = normalize(value);
        if (normalized.length() < 2) {
            return true;
        }
        if (kind == ValueKind.KEYWORD) {
            return normalized.equals("video")
                    || normalized.equals("reel")
                    || normalized.equals("영상")
                    || normalized.equals("콘텐츠")
                    || normalized.equals("instagram")
                    || normalized.equals("youtube");
        }
        return false;
    }

    private enum ValueKind {
        CATEGORY,
        KEYWORD,
        ENTITY
    }
}
