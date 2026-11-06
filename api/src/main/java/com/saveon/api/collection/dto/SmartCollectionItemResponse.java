package com.saveon.api.collection.dto;

public record SmartCollectionItemResponse(
        Long contentId,
        String title,
        String summary,
        String platform,
        String sourceUrl
) {
}
