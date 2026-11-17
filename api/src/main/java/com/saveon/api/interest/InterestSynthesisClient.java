package com.saveon.api.interest;

import com.saveon.api.content.connection.dto.ContentHighlightResponse;
import com.saveon.api.content.connection.dto.RelatedEntityResponse;
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
public class InterestSynthesisClient {

    private final JsonMapper jsonMapper;
    private final String interestAgentBaseUrl;

    public InterestSynthesisClient(
            @Value("${saveon.interest-agent.base-url:http://localhost:8001}")
            String interestAgentBaseUrl
    ) {
        this.interestAgentBaseUrl =
                interestAgentBaseUrl.replaceAll("/+$", "");
        this.jsonMapper =
                JsonMapper.builder().build();
    }

    public AiInterestSynthesisResponse synthesize(
            String entity,
            String type,
            long count,
            String fallbackOverview,
            List<String> categories,
            List<String> commonKeywords,
            List<String> commonTags,
            List<RelatedEntityResponse> relatedEntities,
            List<ContentHighlightResponse> highlights
    ) {
        HttpURLConnection connection = null;

        try {
            Map<String, Object> request =
                    new LinkedHashMap<>();

            request.put("entity", entity);
            request.put("type", type);
            request.put("count", count);
            request.put("fallbackOverview", fallbackOverview);
            request.put("categories", categories);
            request.put("commonKeywords", commonKeywords);
            request.put("commonTags", commonTags);
            request.put("relatedEntities", relatedEntities);
            request.put("highlights", highlights);

            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(request);

            connection =
                    (HttpURLConnection)
                            URI.create(
                                    interestAgentBaseUrl
                                            + "/synthesize"
                            )
                            .toURL()
                            .openConnection();

            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(3_000);
            connection.setReadTimeout(15_000);
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
                        "Interest Agent HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            return jsonMapper.readValue(
                    responseBody,
                    AiInterestSynthesisResponse.class
            );

        } catch (Exception error) {
            throw new RuntimeException(
                    "Interest Synthesis Agent 요청 실패: "
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
