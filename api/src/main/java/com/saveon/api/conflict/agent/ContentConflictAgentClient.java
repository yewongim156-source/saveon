package com.saveon.api.conflict.agent;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class ContentConflictAgentClient {

    private final String baseUrl;
    private final JsonMapper jsonMapper;

    public ContentConflictAgentClient(
            @Value("${saveon.qna-agent.base-url:http://localhost:8003}")
            String baseUrl
    ) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.jsonMapper = JsonMapper.builder().build();
    }

    public ConflictAgentResponse detect(
            List<Map<String, Object>> claims
    ) {
        HttpURLConnection connection = null;

        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("claims", claims);

            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(body);

            connection =
                    (HttpURLConnection)
                            URI.create(baseUrl + "/conflicts/detect")
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(2_500);
            connection.setReadTimeout(25_000);
            connection.setRequestProperty(
                    "Content-Type",
                    "application/json; charset=UTF-8"
            );
            connection.setFixedLengthStreamingMode(requestBody.length);

            try (OutputStream output = connection.getOutputStream()) {
                output.write(requestBody);
                output.flush();
            }

            int status = connection.getResponseCode();
            InputStream responseStream =
                    status >= 200 && status < 300
                            ? connection.getInputStream()
                            : connection.getErrorStream();

            String responseBody = "";

            if (responseStream != null) {
                try (responseStream) {
                    responseBody = new String(
                            responseStream.readAllBytes(),
                            StandardCharsets.UTF_8
                    );
                }
            }

            if (status < 200 || status >= 300) {
                throw new RuntimeException(
                        "Conflict Agent HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            return jsonMapper.readValue(
                    responseBody,
                    ConflictAgentResponse.class
            );

        } catch (Exception error) {
            throw new RuntimeException(
                    "저장물 상충 탐지 Agent 요청 실패: "
                            + error.getMessage(),
                    error
            );
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }
}
