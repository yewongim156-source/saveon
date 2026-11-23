package com.saveon.api.ai;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;

class GeminiLiteServiceTest {

    @Test
    void onlyPublicYouTubeUrlsAreAccepted() {
        GeminiLiteService service = new GeminiLiteService("unconfigured", "gemini-3.5-flash-lite", 20);
        assertThrows(IllegalArgumentException.class,
                () -> service.analyzeYouTube("https://instagram.com/reel/example"));
        assertThrows(IllegalArgumentException.class,
                () -> service.analyzeYouTube("http://youtube.com/shorts/123"));
    }

    @Test
    void blankApiKeyFailsBeforeAnyNetworkRequest() {
        GeminiLiteService service = new GeminiLiteService("", "gemini-3.5-flash-lite", 20);
        assertThrows(IllegalStateException.class,
                () -> service.analyzeYouTube("https://www.youtube.com/shorts/NBRrHibN-K8"));
    }
}
