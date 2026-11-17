package com.saveon.api.action;

import java.util.List;

public record AiActionItemResponse(
        String kind,
        String title,
        String description,
        String query,
        String eventTitle,
        String eventDate,
        List<String> checklistItems
) {
}
