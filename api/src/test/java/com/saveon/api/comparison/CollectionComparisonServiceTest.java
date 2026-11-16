package com.saveon.api.comparison;

import com.saveon.api.comparison.agent.CollectionComparisonAgentClient;
import com.saveon.api.comparison.dto.CollectionComparisonRequest;
import com.saveon.api.content.Content;
import com.saveon.api.content.ContentPlatform;
import com.saveon.api.content.ContentService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.lang.reflect.Field;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.Mockito.*;

class CollectionComparisonServiceTest {
    private Content content(long id, String url, String title) throws Exception {
        Content c = new Content(url, ContentPlatform.YOUTUBE);
        Field field = Content.class.getDeclaredField("id");
        field.setAccessible(true);
        field.set(c, id);
        c.completeAnalysis(title, title, List.of("뷰티"),
                List.of("쿠션"), List.of("잘못된 OCR"), "{}");
        return c;
    }

    @Test
    void findsClioAcrossTitlesWhenEntityDetailsAreMissing() throws Exception {
        ContentService service = mock(ContentService.class);
        CollectionComparisonAgentClient agent = mock(CollectionComparisonAgentClient.class);
        when(service.findById(20L)).thenReturn(content(20, "https://example.com/20", "클리오 킬커버 쿠션 솔직 리뷰"));
        when(service.findById(21L)).thenReturn(content(21, "https://example.com/21", "클리오 메쉬 블러 쿠션 지속력"));
        when(service.findById(23L)).thenReturn(content(23, "https://example.com/23", "NEW 클리오 메쉬 블러 쿠션"));

        new CollectionComparisonService(service, agent).compare(
                new CollectionComparisonRequest("클리오 쿠션", List.of(20L, 21L, 23L)));
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> captured = ArgumentCaptor.forClass(Map.class);
        verify(agent).compare(captured.capture());
        assertEquals("클리오", captured.getValue().get("comparisonEntity"));
        assertEquals(3, ((List<?>) captured.getValue().get("contexts")).size());
    }

    @Test
    void ignoresGenericCushionEntityInFavorOfRepeatedBrand() throws Exception {
        ContentService service = mock(ContentService.class);
        CollectionComparisonAgentClient agent = mock(CollectionComparisonAgentClient.class);
        Content first = content(20, "https://example.com/20", "클리오 쿠션 리뷰");
        Content second = content(23, "https://example.com/23", "클리오 쿠션 런칭");
        first.getEntities().add("쿠션");
        second.getEntities().add("쿠션");
        when(service.findById(20L)).thenReturn(first);
        when(service.findById(23L)).thenReturn(second);

        new CollectionComparisonService(service, agent).compare(
                new CollectionComparisonRequest("클리오 쿠션", List.of(20L, 23L)));
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> captured = ArgumentCaptor.forClass(Map.class);
        verify(agent).compare(captured.capture());
        assertEquals("클리오", captured.getValue().get("comparisonEntity"));
    }

    @Test
    void preventsComparingTwoSavesOfOneVideo() throws Exception {
        ContentService service = mock(ContentService.class);
        CollectionComparisonAgentClient agent = mock(CollectionComparisonAgentClient.class);
        when(service.findById(12L)).thenReturn(content(12, "https://example.com/same?utm_source=one", "올리브영 팁"));
        when(service.findById(13L)).thenReturn(content(13, "https://example.com/same?utm_source=two", "올리브영 팁"));

        var result = new CollectionComparisonService(service, agent).compare(
                new CollectionComparisonRequest("올리브영", List.of(12L, 13L)));
        assertFalse(result.eligible());
        verifyNoInteractions(agent);
    }

    @Test
    void differentYouTubeWatchIdsAreThreeComparisonContexts() throws Exception {
        ContentService service = mock(ContentService.class);
        CollectionComparisonAgentClient agent = mock(CollectionComparisonAgentClient.class);
        when(service.findById(20L)).thenReturn(content(20,
                "https://www.youtube.com/watch?v=AAA11111111", "클리오 쿠션 리뷰"));
        when(service.findById(21L)).thenReturn(content(21,
                "https://www.youtube.com/watch?v=BBB22222222&t=20", "클리오 쿠션 지속력"));
        when(service.findById(23L)).thenReturn(content(23,
                "https://www.youtube.com/watch?feature=share&v=CCC33333333", "클리오 쿠션 출시"));

        new CollectionComparisonService(service, agent).compare(
                new CollectionComparisonRequest("클리오 쿠션", List.of(20L, 21L, 23L)));
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> captured = ArgumentCaptor.forClass(Map.class);
        verify(agent).compare(captured.capture());
        assertEquals(3, ((List<?>) captured.getValue().get("contexts")).size());
        assertEquals("클리오", captured.getValue().get("comparisonEntity"));
    }
}
