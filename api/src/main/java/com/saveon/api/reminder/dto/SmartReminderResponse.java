package com.saveon.api.reminder.dto;

import java.util.List;

public record SmartReminderResponse(
        String key,
        String type,
        String title,
        String description,
        String badge,
        Long contentId,
        String contentTitle,
        String sourceUrl,
        List<String> evidence,
        int score
) {
}
