package com.saveon.api.quality.correction.dto;

import java.util.Map;

public record CorrectionStatsResponse(
        long totalCorrections,
        Map<String, Long> errorTypes
) {
}
