package com.saveon.api.quality.correction.dto;

import java.util.List;

public record ContentCorrectionRequest(
        String title,
        String summary,
        List<String> categories,
        List<String> keywords,
        List<EntityCorrectionRequest> entityDetails
) {
}
