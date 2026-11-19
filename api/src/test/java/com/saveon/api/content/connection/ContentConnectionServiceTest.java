package com.saveon.api.content.connection;

import com.saveon.api.content.Content;
import com.saveon.api.content.ContentPlatform;
import com.saveon.api.content.ContentRepository;
import com.saveon.api.content.connection.dto.ContentConnectionResponse;
import com.saveon.api.interest.InterestSynthesisClient;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ContentConnectionServiceTest {

    private static final String BRAND =
            "{\"entityDetails\":[{\"name\":\"페리페라\",\"type\":\"BRAND\",\"confidence\":0.95}]}";

    private Content content(long id, String url, String structured) throws Exception {
        Content c = new Content(url, ContentPlatform.YOUTUBE);
        Field idField = Content.class.getDeclaredField("id");
        idField.setAccessible(true);
        idField.set(c, id);
        c.completeAnalysis("제목 " + id, "요약", List.of("뷰티/패션"),
                List.of("키워드"), List.of("페리페라"), structured);
        return c;
    }

    private ContentConnectionService service(Content... contents) {
        ContentRepository repository = mock(ContentRepository.class);
        when(repository.findAll()).thenReturn(List.of(contents));
        return new ContentConnectionService(repository, mock(InterestSynthesisClient.class));
    }

    @Test
    void sameVideoSavedSeveralTimesCountsOnce() throws Exception {
        ContentConnectionService service = service(
                content(6, "https://www.youtube.com/shorts/AAA11111111", BRAND),
                content(16, "https://www.youtube.com/shorts/AAA11111111", BRAND),
                content(28, "https://www.youtube.com/shorts/AAA11111111?feature=share", BRAND));

        assertTrue(service.findConnections(null, 10).isEmpty(),
                "one source video is not a repeated topic");
        assertEquals(List.of(28L),
                service.findConnectedContents("BRAND", "페리페라").stream().map(Content::getId).toList(),
                "the newest save stands for the source");
    }

    @Test
    void differentVideosStillFormATopic() throws Exception {
        ContentConnectionService service = service(
                content(6, "https://www.youtube.com/shorts/AAA11111111", BRAND),
                content(16, "https://www.youtube.com/shorts/AAA11111111", BRAND),
                content(30, "https://www.youtube.com/shorts/BBB22222222", BRAND));

        List<ContentConnectionResponse> connections = service.findConnections(null, 10);

        assertEquals(1, connections.size());
        assertEquals("페리페라", connections.get(0).entity());
        assertEquals(2, connections.get(0).count());
        assertEquals(List.of(30L, 16L),
                service.findConnectedContents("BRAND", "페리페라").stream().map(Content::getId).toList());
    }
}
