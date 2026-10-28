package com.saveon.api.ai;

import java.util.List;
import java.util.Map;

import tools.jackson.databind.json.JsonMapper;

public record AiAnalyzeResponse(
        String title,
        String summary,
        List<String> categories,
        List<String> keywords,
        List<String> entities,
        Map<String, Object> structured
) {
    public String structuredJson() {
        try {
            return JsonMapper.builder()
                    .build()
                    .writeValueAsString(
                            structured != null
                                    ? structured
                                    : Map.of()
                    );
        } catch (Exception e) {
            throw new IllegalStateException(
                    "구조화 분석 결과를 JSON으로 변환할 수 없습니다.",
                    e
            );
        }
    }

    public String embeddingText() {
        return String.join(
                "\n",
                title != null ? title : "",
                summary != null ? summary : "",
                "카테고리: " + String.join(", ", categories != null ? categories : List.of()),
                "키워드: " + String.join(", ", keywords != null ? keywords : List.of()),
                "엔티티: " + String.join(", ", entities != null ? entities : List.of())
        ).trim();
    }
}
