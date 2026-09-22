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

    public AiClient(
            @Value("${saveon.ai.base-url}")
            String aiBaseUrl
    ) {
        this.aiBaseUrl = aiBaseUrl;

        this.jsonMapper =
                JsonMapper.builder().build();
    }

    public AiAnalyzeResponse analyze(
            String sourceUrl
    ) {
        HttpURLConnection connection = null;

        try {
            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(
                            new AiAnalyzeRequest(sourceUrl)
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
            connection.setFixedLengthStreamingMode(
                    requestBody.length
            );

            try (
                    OutputStream output =
                            connection.getOutputStream()
            ) {
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

    public AiAnalyzeResponse analyzeVideo(
            MultipartFile file
    ) {
        HttpURLConnection connection = null;

        try {
            byte[] videoBytes =
                    file.getBytes();

            String contentType =
                    file.getContentType() != null
                            ? file.getContentType()
                            : "application/octet-stream";

            System.out.println(
                    "FastAPI RAW 영상 전송 시작: "
                            + videoBytes.length
                            + " bytes"
            );

            connection =
                    (HttpURLConnection)
                            URI.create(
                                    aiBaseUrl
                                            + "/analyze-video-raw"
                            )
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(10_000);
            connection.setReadTimeout(300_000);

            connection.setRequestProperty(
                    "Content-Type",
                    contentType
            );

            connection.setRequestProperty(
                    "X-Filename",
                    "upload.mp4"
            );

            connection.setFixedLengthStreamingMode(
                    videoBytes.length
            );

            try (
                    OutputStream output =
                            connection.getOutputStream()
            ) {
                output.write(videoBytes);
                output.flush();
            }

            int status =
                    connection.getResponseCode();

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
                    "FastAPI HTTP status: "
                            + status
            );

            System.out.println(
                    "FastAPI response: "
                            + responseBody
            );

            if (status < 200 || status >= 300) {
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
                    "❌ FastAPI RAW 영상 전송 오류"
            );

            e.printStackTrace();

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
