package com.saveon.api.ai;

import java.util.List;

public record AiAnalyzeResponse(
        String title,
        String summary,
        List<String> categories,
        List<String> keywords,
        List<String> entities
) {
}