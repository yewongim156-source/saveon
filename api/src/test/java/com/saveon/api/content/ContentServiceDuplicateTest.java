package com.saveon.api.content;

import com.saveon.api.ai.AiClient;
import com.saveon.api.content.dto.CreateContentRequest;
import com.saveon.api.quality.canonical.CanonicalEntityService;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ContentServiceDuplicateTest {

    private Content saved(long id, String url, boolean completed) throws Exception {
        Content c = new Content(url, ContentPlatform.YOUTUBE);
        Field idField = Content.class.getDeclaredField("id");
        idField.setAccessible(true);
        idField.set(c, id);
        if (completed) {
            c.completeAnalysis("제목", "요약", List.of("기타"), List.of(), List.of(), "{}");
        } else {
            c.failAnalysis();
        }
        return c;
    }

    private ContentService service(ContentRepository repository, ContentAnalysisWorker worker) {
        return new ContentService(repository, mock(AiClient.class), worker,
                mock(CanonicalEntityService.class), 20, 50);
    }

    @Test
    void savingTheSameVideoAgainReturnsTheExistingItem() throws Exception {
        ContentRepository repository = mock(ContentRepository.class);
        ContentAnalysisWorker worker = mock(ContentAnalysisWorker.class);
        Content older = saved(6, "https://www.youtube.com/shorts/AAA11111111", true);
        Content newest = saved(29, "https://www.youtube.com/shorts/AAA11111111?feature=share", true);
        when(repository.findAll()).thenReturn(List.of(older, newest));

        Content result = service(repository, worker).create(
                new CreateContentRequest("https://youtu.be/AAA11111111", ContentPlatform.YOUTUBE, false));

        assertSame(newest, result);
        verify(repository, never()).save(any());
        verify(worker, never()).analyzeUrl(any());
    }

    @Test
    void aFailedItemIsAnalyzedAgainInsteadOfDuplicated() throws Exception {
        ContentRepository repository = mock(ContentRepository.class);
        ContentAnalysisWorker worker = mock(ContentAnalysisWorker.class);
        Content failed = saved(7, "https://www.youtube.com/shorts/BBB22222222", false);
        when(repository.findAll()).thenReturn(List.of(failed));
        when(repository.save(any(Content.class))).thenAnswer(call -> call.getArgument(0));

        Content result = service(repository, worker).create(
                new CreateContentRequest("https://www.youtube.com/shorts/BBB22222222", ContentPlatform.YOUTUBE, false));

        assertSame(failed, result);
        verify(worker).analyzeUrl(7L);
    }

    @Test
    void uploadsAndBlankAddressesAreNeverTreatedAsTheSameSource() throws Exception {
        ContentRepository repository = mock(ContentRepository.class);
        Content upload = saved(8, "upload://clip.mp4", true);
        when(repository.findAll()).thenReturn(List.of(upload));
        ContentService service = service(repository, mock(ContentAnalysisWorker.class));

        assertNull(service.findExistingBySource("upload://clip.mp4"));
        assertNull(service.findExistingBySource(""));
        assertNull(service.findExistingBySource(null));
    }
}
