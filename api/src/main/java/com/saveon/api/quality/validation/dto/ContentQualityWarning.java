package com.saveon.api.quality.validation.dto;

public record ContentQualityWarning(
        String type,
        String field,
        String severity,
        String message
) {
}
