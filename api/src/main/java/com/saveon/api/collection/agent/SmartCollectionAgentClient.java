package com.saveon.api.collection.agent;

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
public class SmartCollectionAgentClient {

    private final String baseUrl;
    private final JsonMapper jsonMapper;

    public SmartCollectionAgentClient(
            @Value("${saveon.qna-agent.base-url:http://localhost:8003}")
            String baseUrl
    ) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.jsonMapper = JsonMapper.builder().build();
    }

    public SmartCollectionNameResponse name(
            String seed,
            List<String> titles,
            List<String> summaries,
            List<String> categories,
            List<String> keywords,
            List<String> entities
    ) {
        HttpURLConnection connection = null;

        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("seed", seed);
            body.put("titles", titles);
            body.put("summaries", summaries);
            body.put("categories", categories);
            body.put("keywords", keywords);
            body.put("entities", entities);

            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(body);

            connection =
                    (HttpURLConnection)
                            URI.create(
                                    baseUrl + "/collections/name"
                            )
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(2_500);
            connection.setReadTimeout(15_000);
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
                        "Collection Agent HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            return jsonMapper.readValue(
                    responseBody,
                    SmartCollectionNameResponse.class
            );

        } catch (Exception error) {
            throw new RuntimeException(
                    "스마트 컬렉션 이름 생성 실패: "
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
