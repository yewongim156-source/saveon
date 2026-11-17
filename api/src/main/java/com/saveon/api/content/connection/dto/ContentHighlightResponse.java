package com.saveon.api.content.connection.dto;

public record ContentHighlightResponse(
        Long contentId,
        String title,
        String summary
) {
}
