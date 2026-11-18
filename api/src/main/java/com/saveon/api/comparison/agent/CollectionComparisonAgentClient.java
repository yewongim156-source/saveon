package com.saveon.api.comparison.agent;

import com.saveon.api.comparison.dto.CollectionComparisonResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Map;

@Component
public class CollectionComparisonAgentClient {

    private final String baseUrl;
    private final JsonMapper jsonMapper;

    public CollectionComparisonAgentClient(
            @Value("${saveon.qna-agent.base-url:http://localhost:8003}")
            String baseUrl
    ) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.jsonMapper = JsonMapper.builder().build();
    }

    public CollectionComparisonResponse compare(
            Map<String, Object> body
    ) {
        HttpURLConnection connection = null;

        try {
            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(body);

            connection =
                    (HttpURLConnection)
                            URI.create(
                                    baseUrl + "/collections/compare"
                            )
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(3_000);
            connection.setReadTimeout(55_000);
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

            InputStream responseStream =
                    status >= 200 && status < 300
                            ? connection.getInputStream()
                            : connection.getErrorStream();

            String responseBody = "";

            if (responseStream != null) {
                try (responseStream) {
                    responseBody =
                            new String(
                                    responseStream.readAllBytes(),
                                    StandardCharsets.UTF_8
                            );
                }
            }

            if (status < 200 || status >= 300) {
                throw new RuntimeException(
                        "Comparison Agent HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            return jsonMapper.readValue(
                    responseBody,
                    CollectionComparisonResponse.class
            );

        } catch (Exception error) {
            throw new RuntimeException(
                    "컬렉션 비교 요청 실패: "
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
