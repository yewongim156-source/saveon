package com.saveon.api.quality.validation.dto;

import java.util.List;

public record ContentQualityResponse(
        boolean valid,
        boolean requiresReview,
        List<ContentQualityWarning> warnings
) {
}
