package com.saveon.api.content.connection.dto;

import java.util.List;

public record ContentBundleResponse(
        String entity,
        String type,
        long count,
        String overview,
        List<String> categories,
        List<String> commonKeywords,
        List<String> commonTags,
        List<RelatedEntityResponse> relatedEntities,
        List<ContentHighlightResponse> highlights
) {
}
