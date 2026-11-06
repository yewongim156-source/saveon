package com.saveon.api.conflict.dto;

import java.util.List;

public record ContentConflictResponse(
        String key,
        String subject,
        String claimType,
        String title,
        String description,
        String severity,
        List<ContentConflictEvidenceResponse> evidences,
        String source
) {
}
