package com.saveon.api.action;

import com.saveon.api.content.connection.dto.ContentBundleResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.time.LocalDate;
import java.time.ZoneId;

@Component
public class ActionAgentClient {

    private final JsonMapper jsonMapper;
    private final String actionAgentBaseUrl;

    public ActionAgentClient(
            @Value("${saveon.action-agent.base-url:http://localhost:8002}")
            String actionAgentBaseUrl
    ) {
        this.actionAgentBaseUrl =
                actionAgentBaseUrl.replaceAll("/+$", "");
        this.jsonMapper =
                JsonMapper.builder().build();
    }

    public AiActionPlanResponse plan(
            ContentBundleResponse bundle
    ) {
        Map<String, Object> request =
                new LinkedHashMap<>();

        request.put("contextType", "CONTENT_BUNDLE");
        request.put("entity", bundle.entity());
        request.put("type", bundle.type());
        request.put("count", bundle.count());
        request.put("title", "");
        request.put("summary", bundle.overview());
        request.put("categories", bundle.categories());
        request.put("commonKeywords", bundle.commonKeywords());
        request.put("commonTags", bundle.commonTags());
        request.put("relatedEntities", bundle.relatedEntities());
        request.put("entityDetails", java.util.List.of());
        request.put("highlights", bundle.highlights());
        request.put("contentTypes", bundle.contentTypes());
        request.put("actionFacts", bundle.actionFacts());
        request.put("synthesis", bundle.synthesis());

        return plan(request);
    }


    public AiActionPlanResponse plan(
            Map<String, Object> input
    ) {
        HttpURLConnection connection = null;

        try {
            Map<String, Object> request =
                    new LinkedHashMap<>(input);

            request.putIfAbsent(
                    "currentDate",
                    LocalDate.now(
                            ZoneId.of("Asia/Seoul")
                    ).toString()
            );
            request.putIfAbsent(
                    "timezone",
                    "Asia/Seoul"
            );

            byte[] requestBody =
                    jsonMapper.writeValueAsBytes(request);

            connection =
                    (HttpURLConnection)
                            URI.create(
                                    actionAgentBaseUrl + "/plan"
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
                        "Action Agent HTTP "
                                + status
                                + ": "
                                + responseBody
                );
            }

            return jsonMapper.readValue(
                    responseBody,
                    AiActionPlanResponse.class
            );

        } catch (Exception error) {
            throw new RuntimeException(
                    "Action Agent 요청 실패: "
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
