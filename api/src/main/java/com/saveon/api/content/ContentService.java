package com.saveon.api.content;

import com.saveon.api.ai.AiAnalyzeResponse;
import com.saveon.api.ai.AiClient;
import com.saveon.api.content.dto.CreateContentRequest;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@Service
public class ContentService {

    private final ContentRepository contentRepository;
    private final AiClient aiClient;

    public ContentService(
            ContentRepository contentRepository,
            AiClient aiClient
    ) {
        this.contentRepository = contentRepository;
        this.aiClient = aiClient;
    }

    public Content create(
            CreateContentRequest request
    ) {
        Content content =
                new Content(
                        request.sourceUrl(),
                        request.platform()
                );

        content =
                contentRepository.save(content);

        return analyze(content);
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
                contentRepository.save(content);

        try {
            content.startAnalysis();

            content =
                    contentRepository.save(content);

            AiAnalyzeResponse result =
                    aiClient.analyzeVideo(file);

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
                    result.entities()
            );

        } catch (Exception e) {

            System.err.println(
                    "영상 AI 분석 실패: "
                            + e.getMessage()
            );

            content.failAnalysis();
        }

        return contentRepository.save(content);
    }

    public Content analyze(
            Content content
    ) {
        try {
            content.startAnalysis();

            content =
                    contentRepository.save(content);

            AiAnalyzeResponse result =
                    aiClient.analyze(
                            content.getSourceUrl()
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
                    result.entities()
            );

        } catch (Exception e) {

            System.err.println(
                    "AI 분석 실패: "
                            + e.getMessage()
            );

            content.failAnalysis();
        }

        return contentRepository.save(content);
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
