package com.saveon.api.content;

import com.saveon.api.ai.AiAnalyzeResponse;
import com.saveon.api.ai.AiClient;
import com.saveon.api.quality.canonical.CanonicalEntityService;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Service
public class ContentAnalysisWorker {

    private final ContentRepository contentRepository;
    private final AiClient aiClient;
    private final CanonicalEntityService canonicalEntityService;

    public ContentAnalysisWorker(
            ContentRepository contentRepository,
            AiClient aiClient,
            CanonicalEntityService canonicalEntityService
    ) {
        this.contentRepository =
                contentRepository;

        this.aiClient =
                aiClient;

        this.canonicalEntityService =
                canonicalEntityService;
    }


    @Async("aiTaskExecutor")
    public void analyzeUrl(
            Long contentId
    ) {
        System.out.println(
                "🚀 비동기 AI 분석 시작: contentId="
                        + contentId
        );

        try {
            Content content =
                    contentRepository
                            .findById(contentId)
                            .orElseThrow(
                                    () ->
                                            new IllegalArgumentException(
                                                    "Content not found: "
                                                            + contentId
                                            )
                            );

            AiAnalyzeResponse result =
                    aiClient.analyze(
                            content.getSourceUrl()
                    );

            if (result == null) {
                throw new IllegalStateException(
                        "AI 서버 응답이 비어 있습니다."
                );
            }

            Content latest =
                    contentRepository
                            .findById(contentId)
                            .orElseThrow(
                                    () ->
                                            new IllegalArgumentException(
                                                    "Content not found: "
                                                            + contentId
                                            )
                            );

            latest.completeAnalysis(
                    result.title(),
                    result.summary(),
                    result.categories(),
                    result.keywords(),
                    result.entities(),
                    result.structuredJson()
            );

            boolean canonicalApplied =
                    canonicalEntityService
                            .applyKnownEntities(
                                    latest
                            );

            if (canonicalApplied) {
                System.out.println(
                        "🧠 Canonical entity 자동 보정 적용: contentId="
                                + contentId
                );
            }

            try {
                var embeddingResult =
                        aiClient.embed(
                                result.embeddingText()
                        );

                latest.setEmbedding(
                        embeddingResult.asArray(),
                        embeddingResult.model(),
                        result.embeddingText()
                );

            } catch (Exception embeddingError) {
                System.err.println(
                        "⚠️ 임베딩 생성 실패 - 분석 결과는 유지: "
                                + embeddingError.getMessage()
                );
            }

            contentRepository.save(
                    latest
            );

            System.out.println(
                    "✅ 비동기 AI 분석 완료: contentId="
                            + contentId
            );

        } catch (Exception e) {
            System.err.println(
                    "❌ 비동기 AI 분석 실패: contentId="
                            + contentId
                            + " / "
                            + e.getMessage()
            );

            contentRepository
                    .findById(contentId)
                    .ifPresent(
                            content -> {
                                content.failAnalysis();
                                contentRepository.save(
                                        content
                                );
                            }
                    );
        }
    }
}
