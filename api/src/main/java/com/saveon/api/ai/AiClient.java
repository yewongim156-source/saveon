package com.saveon.api.ai;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import tools.jackson.databind.json.JsonMapper;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;

@Component
public class AiClient {

    private final JsonMapper jsonMapper;
    private final String aiBaseUrl;
    private final String aiMode;
    private final GeminiLiteService geminiLiteService;

    public AiClient(
            @Value("${saveon.ai.base-url}") String aiBaseUrl,
            @Value("${SAVEON_AI_MODE:local}") String aiMode,
            GeminiLiteService geminiLiteService
    ) {
        this.aiBaseUrl = aiBaseUrl;
        this.aiMode = aiMode;
        this.geminiLiteService = geminiLiteService;
        this.jsonMapper = JsonMapper.builder().build();
    }

    // save:on TRUE_PROGRESS_V1: preserve old callers.
    public AiAnalyzeResponse analyze(String sourceUrl) {
        return analyze(sourceUrl, null);
    }

    public AiAnalyzeResponse analyze(String sourceUrl, Long contentId) {
        return analyze(sourceUrl, contentId, false);
    }

    public AiAnalyzeResponse analyze(String sourceUrl, Long contentId,
            boolean thumbnailRequested) {
        if ("gemini-lite".equalsIgnoreCase(aiMode)) {
            return geminiLiteService.analyzeYouTube(sourceUrl);
        }
        HttpURLConnection connection = null;

        try {
            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(
                            java.util.Map.of("sourceUrl", sourceUrl, "thumbnailRequested", thumbnailRequested)
                    );

            connection =
                    (HttpURLConnection)
                            URI.create(
                                    aiBaseUrl + "/analyze"
                            )
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(10_000);
            connection.setReadTimeout(1_800_000);
            connection.setRequestProperty(
                    "Content-Type",
                    "application/json; charset=UTF-8"
            );
            if (contentId != null) {
                connection.setRequestProperty(
                        "X-Saveon-Content-Id",
                        contentId.toString()
                );
            }
            connection.setFixedLengthStreamingMode(
                    requestBody.length
            );

            try (OutputStream output =
                         connection.getOutputStream()) {
                output.write(requestBody);
                output.flush();
            }

            int status = connection.getResponseCode();
            InputStream input =
                    status >= 200 && status < 300
                            ? connection.getInputStream()
                            : connection.getErrorStream();

            String responseBody;
            if (input != null) {
                try (input) {
                    responseBody =
                            new String(
                                    input.readAllBytes(),
                                    StandardCharsets.UTF_8
                            );
                }
            } else {
                responseBody = "";
            }

            if (status < 200 || status >= 300) {
                throw new RuntimeException(
                        "FastAPI HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            return jsonMapper.readValue(
                    responseBody,
                    AiAnalyzeResponse.class
            );

        } catch (Exception e) {
            throw new RuntimeException(
                    "FastAPI URL 분석 요청 실패: "
                            + e.getMessage(),
                    e
            );
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    public AiEmbedResponse embed(
            String text
    ) {
        if ("gemini-lite".equalsIgnoreCase(aiMode)) {
            return geminiLiteService.embed(text);
        }
        HttpURLConnection connection = null;

        try {
            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(
                            new AiEmbedRequest(text)
                    );

            connection =
                    (HttpURLConnection)
                            URI.create(
                                    aiBaseUrl + "/embed"
                            )
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(10_000);
            connection.setReadTimeout(60_000);
            connection.setRequestProperty(
                    "Content-Type",
                    "application/json; charset=UTF-8"
            );
            connection.setFixedLengthStreamingMode(
                    requestBody.length
            );

            try (OutputStream output =
                         connection.getOutputStream()) {
                output.write(requestBody);
                output.flush();
            }

            int status = connection.getResponseCode();
            InputStream input =
                    status >= 200 && status < 300
                            ? connection.getInputStream()
                            : connection.getErrorStream();

            String responseBody;
            if (input != null) {
                try (input) {
                    responseBody =
                            new String(
                                    input.readAllBytes(),
                                    StandardCharsets.UTF_8
                            );
                }
            } else {
                responseBody = "";
            }

            if (status < 200 || status >= 300) {
                throw new RuntimeException(
                        "FastAPI HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            AiEmbedResponse result =
                    jsonMapper.readValue(
                            responseBody,
                            AiEmbedResponse.class
                    );

            if (result.dimensions() != 768
                    || result.vector() == null
                    || result.vector().size() != 768) {
                throw new IllegalStateException(
                        "임베딩은 768차원이어야 합니다."
                );
            }

            return result;

        } catch (Exception e) {
            throw new RuntimeException(
                    "FastAPI 임베딩 요청 실패: "
                            + e.getMessage(),
                    e
            );
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    public AiAnalyzeResponse analyzeVideo(
            MultipartFile file
    ) {
        HttpURLConnection connection = null;

        try {
            if (file == null || file.isEmpty()) {
                throw new IllegalArgumentException(
                        "업로드된 영상 파일이 비어 있습니다."
                );
            }

            byte[] videoBytes = file.getBytes();

            if (videoBytes.length == 0) {
                throw new IllegalArgumentException(
                        "영상 바이트가 0 bytes여서 AI 서버로 전송하지 않았습니다."
                );
            }

            String originalFilename =
                    file.getOriginalFilename() != null
                            ? file.getOriginalFilename()
                            : "upload.mp4";

            String contentType =
                    file.getContentType() != null
                            ? file.getContentType()
                            : "application/octet-stream";

            System.out.println(
                    "FastAPI RAW 영상 전송 시작: "
                            + originalFilename
                            + " / "
                            + videoBytes.length
                            + " bytes"
            );

            connection =
                    (HttpURLConnection)
                            URI.create(
                                    aiBaseUrl + "/analyze-video-raw"
                            )
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(10_000);
            connection.setReadTimeout(1_800_000);
            connection.setRequestProperty(
                    "Content-Type",
                    contentType
            );
            connection.setRequestProperty(
                    "X-Filename",
                    originalFilename
            );
            connection.setFixedLengthStreamingMode(
                    videoBytes.length
            );

            try (OutputStream output =
                         connection.getOutputStream()) {
                output.write(videoBytes);
                output.flush();
            }

            int status = connection.getResponseCode();

            InputStream input =
                    status >= 200 && status < 300
                            ? connection.getInputStream()
                            : connection.getErrorStream();

            String responseBody;
            if (input != null) {
                try (input) {
                    responseBody =
                            new String(
                                    input.readAllBytes(),
                                    StandardCharsets.UTF_8
                            );
                }
            } else {
                responseBody = "";
            }

            System.out.println(
                    "FastAPI HTTP status: " + status
            );

            if (status < 200 || status >= 300) {
                System.err.println(
                        "FastAPI response: " + responseBody
                );
                throw new RuntimeException(
                        "FastAPI HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            AiAnalyzeResponse result =
                    jsonMapper.readValue(
                            responseBody,
                            AiAnalyzeResponse.class
                    );

            System.out.println(
                    "✅ FastAPI RAW 영상 분석 응답 성공"
            );

            return result;

        } catch (Exception e) {
            System.err.println(
                    "❌ FastAPI RAW 영상 전송 오류: "
                            + e.getMessage()
            );

            throw new RuntimeException(
                    "FastAPI 영상 전송 실패: "
                            + e.getMessage(),
                    e
            );

        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }
}

// save:on TRUE_PROGRESS_V1
// SAVEON_INSTAGRAM_THUMBNAIL_V1
