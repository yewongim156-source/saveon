package com.saveon.api.content.connection.dto;

public record ContentActionFactResponse(
        Long contentId,
        String text,
        String type,
        double confidence
) {
}
