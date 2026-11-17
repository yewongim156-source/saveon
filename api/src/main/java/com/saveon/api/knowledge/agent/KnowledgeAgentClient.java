package com.saveon.api.knowledge.agent;

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
public class KnowledgeAgentClient {

    private final JsonMapper jsonMapper;
    private final String baseUrl;

    public KnowledgeAgentClient(
            @Value("${saveon.qna-agent.base-url:http://localhost:8003}")
            String baseUrl
    ) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.jsonMapper = JsonMapper.builder().build();
    }

    public KnowledgeAgentResponse ask(
            String question,
            List<Map<String, Object>> contexts
    ) {
        HttpURLConnection connection = null;

        try {
            Map<String, Object> request = new LinkedHashMap<>();
            request.put("question", question);
            request.put("contexts", contexts);

            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(request);

            connection =
                    (HttpURLConnection)
                            URI.create(baseUrl + "/ask")
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(3_000);
            connection.setReadTimeout(30_000);
            connection.setRequestProperty(
                    "Content-Type",
                    "application/json; charset=UTF-8"
            );
            connection.setFixedLengthStreamingMode(
                    requestBody.length
            );

            try (OutputStream output = connection.getOutputStream()) {
                output.write(requestBody);
                output.flush();
            }

            int status = connection.getResponseCode();

            InputStream responseStream =
                    status >= 200 && status < 300
                            ? connection.getInputStream()
                            : connection.getErrorStream();

            String responseBody;

            if (responseStream != null) {
                try (responseStream) {
                    responseBody =
                            new String(
                                    responseStream.readAllBytes(),
                                    StandardCharsets.UTF_8
                            );
                }
            } else {
                responseBody = "";
            }

            if (status < 200 || status >= 300) {
                throw new RuntimeException(
                        "Q&A Agent HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            return jsonMapper.readValue(
                    responseBody,
                    KnowledgeAgentResponse.class
            );

        } catch (Exception error) {
            throw new RuntimeException(
                    "Q&A Agent 요청 실패: "
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
