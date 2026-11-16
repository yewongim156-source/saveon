package com.saveon.api.content;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ContentSourceIdentityTest {
    @Test
    void youtubeWatchVideoIdIsNotDiscardedWithQueryParameters() {
        assertNotEquals(
                ContentSourceIdentity.key("https://www.youtube.com/watch?v=AAA11111111", 20L),
                ContentSourceIdentity.key("https://www.youtube.com/watch?v=BBB22222222", 21L));
        assertEquals("youtube:AAA11111111",
                ContentSourceIdentity.key("https://www.youtube.com/watch?v=AAA11111111&t=20", 20L));
        assertEquals("youtube:AAA11111111",
                ContentSourceIdentity.key("https://youtu.be/AAA11111111?si=xyz", 21L));
        assertEquals("youtube:AAA11111111",
                ContentSourceIdentity.key("https://www.youtube.com/shorts/AAA11111111?feature=share", 22L));
    }

    @Test
    void duplicateReelsStillCollapseToOneSource() {
        assertEquals(
                ContentSourceIdentity.key("https://www.instagram.com/reel/ABC123/?utm_source=one", 12L),
                ContentSourceIdentity.key("https://www.instagram.com/reel/ABC123/?utm_source=two", 13L));
    }

    @Test
    void malformedYouTubeWatchWithoutVideoIdDoesNotCollapseOthers() {
        assertNotEquals(
                ContentSourceIdentity.key("https://www.youtube.com/watch?feature=share", 20L),
                ContentSourceIdentity.key("https://www.youtube.com/watch?feature=share", 21L));
    }
}
