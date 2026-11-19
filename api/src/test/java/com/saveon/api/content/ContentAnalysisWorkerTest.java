package com.saveon.api.content;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ContentAnalysisWorkerTest {

    @Test
    void fallbackResultsAreRecognizedRegardlessOfSpacing() {
        assertTrue(ContentAnalysisWorker.isFallbackResult("{\"analysisQuality\":\"FALLBACK\"}"));
        assertTrue(ContentAnalysisWorker.isFallbackResult("{\n  \"a\": 1,\n  \"analysisQuality\" : \"FALLBACK\"\n}"));
        assertFalse(ContentAnalysisWorker.isFallbackResult("{\"analysisQuality\":\"OK\"}"));
        assertFalse(ContentAnalysisWorker.isFallbackResult("{}"));
        assertFalse(ContentAnalysisWorker.isFallbackResult(null));
    }

    @Test
    void aFailedReanalysisKeepsTheSavedSummaryAndCompletesAgain() {
        Content content = new Content("https://www.youtube.com/shorts/AAA11111111", ContentPlatform.YOUTUBE);
        content.completeAnalysis("제목", "좋은 요약", List.of("기타"), List.of(), List.of(), "{}");

        content.startAnalysis();
        assertEquals(ContentStatus.ANALYZING, content.getStatus());

        assertTrue(content.keepPreviousAnalysis());
        assertEquals(ContentStatus.COMPLETED, content.getStatus());
        assertEquals("좋은 요약", content.getSummary());
    }

    @Test
    void withoutAPreviousSummaryNothingIsKept() {
        Content content = new Content("https://www.youtube.com/shorts/BBB22222222", ContentPlatform.YOUTUBE);
        content.startAnalysis();

        assertFalse(content.keepPreviousAnalysis());
        assertEquals(ContentStatus.ANALYZING, content.getStatus());
    }
}
