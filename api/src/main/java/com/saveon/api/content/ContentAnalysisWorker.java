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
    private final InstagramThumbnailStorage thumbnailStorage;
    private final CanonicalEntityService canonicalEntityService;

    public ContentAnalysisWorker(
            ContentRepository contentRepository,
            AiClient aiClient,
            CanonicalEntityService canonicalEntityService,
            InstagramThumbnailStorage thumbnailStorage
    ) {
        this.contentRepository =
                contentRepository;

        this.aiClient =
                aiClient;

        this.canonicalEntityService =
                canonicalEntityService;
        this.thumbnailStorage = thumbnailStorage;
    }


    static boolean isFallbackResult(
            String structuredJson
    ) {
        return structuredJson != null
                && structuredJson.matches(
                "(?s).*\"analysisQuality\"\\s*:\\s*\"FALLBACK\".*"
        );
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
                            content.getSourceUrl(),
                            contentId,
                            content.isThumbnailAllowed()
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

            // 모델 과부하 등으로 AI가 대체(fallback) 결과만 돌려줬다면,
            // 이미 저장된 좋은 요약을 빈 문구로 덮어쓰지 않는다.
            if (isFallbackResult(result.structuredJson())
                    && latest.keepPreviousAnalysis()) {
                contentRepository.save(latest);

                System.out.println(
                        "⚠️ 재분석이 대체 결과여서 기존 분석을 유지: contentId="
                                + contentId
                );
                return;
            }

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

            // Optional preview is attempted BEFORE final DB save, so the mobile
            // client sees COMPLETED and thumbnailAvailable in the same response.
            if (latest.isThumbnailAllowed()
                    && result.thumbnailBase64() != null
                    && !result.thumbnailBase64().isBlank()) {
                try {
                    String key = thumbnailStorage.store(
                            contentId, result.thumbnailBase64()
                    );
                    latest.setThumbnailObjectKey(key);
                    System.out.println("[THUMBNAIL] Stored for contentId=" + contentId);
                } catch (Exception thumbnailError) {
                    System.err.println("[THUMBNAIL] Optional image failed: "
                            + thumbnailError.getClass().getSimpleName());
                }
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

// save:on TRUE_PROGRESS_V1
// SAVEON_INSTAGRAM_THUMBNAIL_V1
