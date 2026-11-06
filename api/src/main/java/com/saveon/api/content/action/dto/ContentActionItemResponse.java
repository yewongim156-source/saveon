package com.saveon.api.content.action.dto;

import java.util.List;

public record ContentActionItemResponse(
        String kind,
        String title,
        String description,
        String query,
        String eventTitle,
        String eventDate,
        List<String> checklistItems
) {
}
