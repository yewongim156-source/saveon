package com.saveon.api.collection;

import com.saveon.api.collection.agent.SmartCollectionAgentClient;
import com.saveon.api.collection.dto.SmartCollectionResponse;
import com.saveon.api.content.Content;
import com.saveon.api.content.ContentPlatform;
import com.saveon.api.content.ContentService;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class SmartCollectionServiceTest {

    private Content content(long id, String url, String title,
                            List<String> keywords, List<String> entities,
                            String structured) throws Exception {
        Content c = new Content(url, ContentPlatform.INSTAGRAM);
        Field idField = Content.class.getDeclaredField("id");
        idField.setAccessible(true);
        idField.set(c, id);
        c.completeAnalysis(title, title, List.of("뷰티/패션"),
                keywords, entities, structured);
        return c;
    }

    @Test
    void clioVideosGroupFromTitleEvenWhenTwoHaveBadOcrEntities() throws Exception {
        ContentService contentService = mock(ContentService.class);
        SmartCollectionAgentClient agent = mock(SmartCollectionAgentClient.class);
        Content generic = content(19, "https://example.com/19", "Video by huyudize",
                List.of("구선", "쿠션", "정리"), List.of("ILSKI"),
                "{\"tags\":[\"쿠션\"],\"entityDetails\":[{\"name\":\"ILSKI\",\"type\":\"OTHER\",\"confidence\":0.0}]}");
        Content twenty = content(20, "https://example.com/20",
                "클리오 킬커버 메쉬 블러 쿠션 솔직 리뷰 및 사용 팁",
                List.of("클리오", "킬커버 메쉬 블러 쿠션"), List.of("클리오"),
                "{\"tags\":[\"클리오\"],\"entityDetails\":[{\"name\":\"클리오\",\"type\":\"BRAND\",\"confidence\":0.99}]}");
        Content twentyOne = content(21, "https://example.com/21",
                "6월 올영세일 쿠션 각? NO광고 클리오 킬커버 메쉬 블러 쿠션 리뷰",
                List.of("쿠션", "클리오", "킬커버"), List.of("CLIO", "OCR 잡음"),
                "{\"tags\":[\"쿠션\",\"클리오\"],\"entityDetails\":[{\"name\":\"CLIO\",\"type\":\"OTHER\",\"confidence\":0.0}]}");
        Content twentyThree = content(23, "https://example.com/23",
                "#쿠션기록 NEW 클리오 메쉬 블러 쿠션 런칭! 모공 블러링",
                List.of("메쉬", "쿠션", "블러"), List.of("OCR 잡음"),
                "{\"tags\":[\"메쉬\",\"쿠션\"],\"entityDetails\":[{\"name\":\"OCR 잡음\",\"type\":\"OTHER\",\"confidence\":0.0}]}");
        when(contentService.findAll()).thenReturn(List.of(generic, twenty, twentyOne, twentyThree));

        List<SmartCollectionResponse> collections = new SmartCollectionService(contentService, agent)
                .findCollections(10);
        SmartCollectionResponse clio = collections.stream()
                .filter(c -> c.seed().equals("클리오"))
                .findFirst().orElseThrow();
        Set<Long> ids = clio.contents().stream()
                .map(item -> item.contentId())
                .collect(Collectors.toSet());
        assertEquals(Set.of(20L, 21L, 23L), ids);
        assertEquals(3, clio.count());
        verify(contentService, never()).semanticSearch(anyString(), any());
    }

    @Test
    void identicalSourceUrlCannotFormACollection() throws Exception {
        ContentService service = mock(ContentService.class);
        SmartCollectionAgentClient agent = mock(SmartCollectionAgentClient.class);
        Content a = content(12, "https://www.instagram.com/reel/DfFFZjtypbI/?utm_source=one",
                "올리브영 블랙프라이데이 쇼핑 꿀팁", List.of("올리브영"), List.of("올리브영"), "{}");
        Content b = content(13, "https://www.instagram.com/reel/DfFFZjtypbI/?utm_source=two",
                "올리브영 블랙프라이데이 쇼핑 꿀팁", List.of("올리브영"), List.of("올리브영"), "{}");
        when(service.findAll()).thenReturn(List.of(a, b));
        assertTrue(new SmartCollectionService(service, agent).findCollections(10).isEmpty());
    }

    @Test
    void clioDistinctYouTubeWatchIdsFormCollection() throws Exception {
        ContentService contentService = mock(ContentService.class);
        SmartCollectionAgentClient agent = mock(SmartCollectionAgentClient.class);
        Content twenty = content(20, "https://www.youtube.com/watch?v=AAA11111111",
                "클리오 킬커버 메쉬 블러 쿠션 솔직 리뷰",
                List.of("클리오", "킬커버 메쉬 블러 쿠션"), List.of("클리오"),
                "{\"entityDetails\":[{\"name\":\"클리오\",\"type\":\"BRAND\",\"confidence\":0.99}]}");
        Content twentyOne = content(21, "https://www.youtube.com/watch?v=BBB22222222&t=13",
                "6월 올영세일 클리오 킬커버 메쉬 블러 쿠션 리뷰",
                List.of("쿠션", "클리오", "킬커버"), List.of("CLIO"), "{}");
        Content twentyThree = content(23, "https://www.youtube.com/watch?feature=share&v=CCC33333333",
                "NEW 클리오 메쉬 블러 쿠션 런칭",
                List.of("메쉬", "쿠션", "블러"), List.of("잘못된 OCR"), "{}");
        Content generic = content(19, "https://www.instagram.com/reel/example19/",
                "Video by huyudize", List.of("쿠션", "정리"), List.of("OCR"), "{}");
        when(contentService.findAll()).thenReturn(List.of(twenty, twentyOne, twentyThree, generic));

        List<SmartCollectionResponse> collections =
                new SmartCollectionService(contentService, agent).findCollections(10);
        SmartCollectionResponse clio = collections.stream()
                .filter(c -> c.seed().equals("클리오"))
                .findFirst().orElseThrow();
        Set<Long> ids = clio.contents().stream().map(item -> item.contentId())
                .collect(Collectors.toSet());
        assertEquals(Set.of(20L, 21L, 23L), ids);
        assertEquals(3, clio.count());
    }
}
