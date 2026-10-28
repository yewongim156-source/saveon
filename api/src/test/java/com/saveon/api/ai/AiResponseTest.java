package com.saveon.api.ai;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AiResponseTest {

    @Test
    void convertsEmbeddingListToPrimitiveArray() {
        AiEmbedResponse response = new AiEmbedResponse(
                "test-model",
                3,
                List.of(0.1f, 0.2f, 0.3f)
        );

        assertArrayEquals(
                new float[]{0.1f, 0.2f, 0.3f},
                response.asArray()
        );
    }

    @Test
    void buildsSearchTextAndStructuredJson() {
        AiAnalyzeResponse response = new AiAnalyzeResponse(
                "성수 카페",
                "성수동 카페 추천",
                List.of("장소/여행"),
                List.of("성수", "카페"),
                List.of("성수역"),
                Map.of("primaryCategory", "장소/여행")
        );

        assertTrue(response.embeddingText().contains("성수동 카페 추천"));
        assertTrue(response.embeddingText().contains("성수역"));
        assertTrue(response.structuredJson().contains("primaryCategory"));
    }
}
