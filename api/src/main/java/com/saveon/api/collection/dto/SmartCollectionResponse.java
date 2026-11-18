package com.saveon.api.collection.dto;

import java.util.List;

public record SmartCollectionResponse(
        String key,
        String seed,
        String title,
        String description,
        int count,
        List<String> categories,
        List<String> commonKeywords,
        List<String> commonEntities,
        List<SmartCollectionItemResponse> contents,
        String source
) {
}
