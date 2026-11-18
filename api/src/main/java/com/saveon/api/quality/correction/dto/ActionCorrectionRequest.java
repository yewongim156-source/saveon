package com.saveon.api.quality.correction.dto;

public record ActionCorrectionRequest(
        Long contentId,
        String fieldName,
        String aiValue,
        String correctedValue,
        String errorType
) {
}
