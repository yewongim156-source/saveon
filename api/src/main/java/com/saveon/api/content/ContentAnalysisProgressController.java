package com.saveon.api.content;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.json.JsonMapper;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.Set;

/** Live progress is advisory; persisted Content.status is authoritative. */
@RestController
@RequestMapping("/api/v1/contents")
@CrossOrigin(origins = "*")
public class ContentAnalysisProgressController {
    private static final Set<String> STAGES = Set.of(
            "UNKNOWN", "STARTING", "DOWNLOADING", "TRANSCRIBING",
            "READING_SCREEN", "SUMMARIZING", "FINALIZING", "FAILED"
    );

    private final ContentRepository repository;
    private final String aiBaseUrl;
    private final JsonMapper mapper = JsonMapper.builder().build();

    public ContentAnalysisProgressController(
            ContentRepository repository,
            @Value("${saveon.ai.base-url}") String aiBaseUrl
    ) {
        this.repository = repository;
        this.aiBaseUrl = aiBaseUrl.replaceAll("/+$", "");
    }

    @GetMapping("/{id}/progress")
    public Map<String, Object> progress(@PathVariable Long id) {
        Content content = repository.findById(id).orElseThrow(
                () -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Content not found")
        );

        String status = content.getStatus().name();
        String stage = switch (status) {
            case "COMPLETED" -> "COMPLETED";
            case "FAILED" -> "FAILED";
            case "PENDING" -> "STARTING";
            default -> fetchAiStage(id);
        };
        return Map.of("contentId", id, "status", status, "stage", stage);
    }

    private String fetchAiStage(Long contentId) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) URI.create(
                    aiBaseUrl + "/progress/" + contentId
            ).toURL().openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(700);
            connection.setReadTimeout(1000);
            if (connection.getResponseCode() != 200) return "UNKNOWN";
            try (InputStream input = connection.getInputStream()) {
                String payload = new String(input.readAllBytes(), StandardCharsets.UTF_8);
                Map<?, ?> json = mapper.readValue(payload, Map.class);
                Object rawStage = json.get("stage");
                String stage = rawStage instanceof String s ? s : "UNKNOWN";
                return STAGES.contains(stage) ? stage : "UNKNOWN";
            }
        } catch (Exception ignored) {
            // AI can restart or be busy. Never fail the normal content status request.
            return "UNKNOWN";
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
