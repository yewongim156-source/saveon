package com.saveon.api.comparison.dto;

import java.util.List;

public record CollectionComparisonRequest(
        String collectionTitle,
        List<Long> contentIds
) {
}
