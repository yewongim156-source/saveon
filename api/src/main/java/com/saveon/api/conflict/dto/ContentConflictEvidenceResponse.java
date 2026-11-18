package com.saveon.api.conflict.dto;

public record ContentConflictEvidenceResponse(
        Long contentId,
        String title,
        String claimText,
        String value
) {
}
