package com.saveon.api.interest.timeline.dto;

import java.util.List;

public record InterestTimelineResponse(
        int recentDays,
        int recentCount,
        int previousCount,
        int last30DaysCount,
        String summary,
        List<TrendItem> categoryTrends,
        List<InterestItem> emergingInterests,
        List<InterestItem> topInterests
) {
    public record TrendItem(
            String label,
            int currentCount,
            int previousCount,
            int delta,
            String direction
    ) {
    }

    public record InterestItem(
            String label,
            String type,
            int count
    ) {
    }
}
