package com.saveon.api.knowledge.dto;

public record KnowledgeSourceResponse(
        Long contentId,
        String title,
        String summary,
        String platform,
        String sourceUrl
) {
}
