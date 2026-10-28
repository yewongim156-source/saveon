package com.saveon.api.content;

import com.saveon.api.ai.AiAnalyzeResponse;
import com.saveon.api.ai.AiClient;
import com.saveon.api.content.dto.CreateContentRequest;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;

import java.util.List;

@Service
public class ContentService {

    private final ContentRepository contentRepository;
    private final AiClient aiClient;
    private final ContentAnalysisWorker contentAnalysisWorker;
    private final int semanticDefaultLimit;
    private final int semanticMaxLimit;

    public ContentService(
            ContentRepository contentRepository,
            AiClient aiClient,
            ContentAnalysisWorker contentAnalysisWorker,
            @Value("${saveon.search.semantic-default-limit:20}")
            int semanticDefaultLimit,
            @Value("${saveon.search.semantic-max-limit:50}")
            int semanticMaxLimit
    ) {
        this.contentRepository =
                contentRepository;

        this.aiClient =
                aiClient;

        this.contentAnalysisWorker =
                contentAnalysisWorker;

        this.semanticDefaultLimit =
                semanticDefaultLimit;

        this.semanticMaxLimit =
                semanticMaxLimit;
    }


    public Content create(
            CreateContentRequest request
    ) {
        Content content =
                new Content(
                        request.sourceUrl(),
                        request.platform()
                );

        content.startAnalysis();

        content =
                contentRepository.save(
                        content
                );

        contentAnalysisWorker.analyzeUrl(
                content.getId()
        );

        return content;
    }


    public Content createFromVideo(
            MultipartFile file
    ) {
        String filename =
                file.getOriginalFilename() != null
                        ? file.getOriginalFilename()
                        : "upload.mp4";

        Content content =
                new Content(
                        "upload://" + filename,
                        ContentPlatform.UPLOAD
                );

        content =
                contentRepository.save(
                        content
                );

        try {
            content.startAnalysis();

            content =
                    contentRepository.save(
                            content
                    );

            AiAnalyzeResponse result =
                    aiClient.analyzeVideo(
                            file
                    );

            if (result == null) {
                throw new IllegalStateException(
                        "AI 서버 응답이 비어 있습니다."
                );
            }

            content.completeAnalysis(
                    result.title(),
                    result.summary(),
                    result.categories(),
                    result.keywords(),
                    result.entities(),
                    result.structuredJson()
            );

            try {
                var embeddingResult =
                        aiClient.embed(
                                result.embeddingText()
                        );

                content.setEmbedding(
                        embeddingResult.asArray(),
                        embeddingResult.model(),
                        result.embeddingText()
                );
            } catch (Exception embeddingError) {
                System.err.println(
                        "임베딩 생성 실패 - 분석 결과는 유지: "
                                + embeddingError.getMessage()
                );
            }

        } catch (Exception e) {

            System.err.println(
                    "영상 AI 분석 실패: "
                            + e.getMessage()
            );

            content.failAnalysis();
        }

        return contentRepository.save(
                content
        );
    }


    public Content analyze(
            Content content
    ) {
        content.startAnalysis();

        content =
                contentRepository.save(
                        content
                );

        contentAnalysisWorker.analyzeUrl(
                content.getId()
        );

        return content;
    }


    public Content analyzeById(
            Long id
    ) {
        Content content =
                findById(id);

        return analyze(content);
    }


    public List<Content> findAll() {
        return contentRepository.findAll();
    }


    public List<Content> search(
            String query
    ) {
        if (query == null) {
            return findAll();
        }

        String searchTerm =
                query.trim();

        if (searchTerm.isEmpty()) {
            return findAll();
        }

        return contentRepository.search(
                searchTerm
        );
    }


    public List<Content> semanticSearch(
            String query,
            Integer requestedLimit
    ) {
        if (query == null || query.trim().isEmpty()) {
            return List.of();
        }

        int limit = requestedLimit != null
                ? requestedLimit
                : semanticDefaultLimit;
        limit = Math.max(
                1,
                Math.min(limit, semanticMaxLimit)
        );

        var embedding =
                aiClient.embed(query.trim());

        return contentRepository.semanticSearch(
                embedding.asArray(),
                PageRequest.of(0, limit)
        );
    }


    public Content findById(
            Long id
    ) {
        return contentRepository
                .findById(id)
                .orElseThrow(
                        () ->
                                new IllegalArgumentException(
                                        "Content not found: "
                                                + id
                                )
                );
    }
}
