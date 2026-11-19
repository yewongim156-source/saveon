package com.saveon.api.content;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ObjectNode;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Pattern;

@RestController
@RequestMapping("/api/v1/internal/evaluation-publications")
public class EvaluationPublicationController {
    private static final Pattern REEL = Pattern.compile(
            "^https?://(?:www\\.|m\\.)?instagram\\.com/reel/([a-zA-Z0-9_-]+)/?(?:[?#].*)?$");
    private static final List<String> SUMMARY_FIELDS = List.of(
            "targets", "globalSteps", "videoEvidence", "ocrEvidence", "videoObservations",
            "externalReferences", "claims", "factChecks", "verificationStatus", "verifiedSummary",
            "verifiedFacts", "corrections", "unverifiedNotes", "rawSummary", "summarySource",
            "analysisQuality", "promptVariant");

    private final ContentRepository repository;
    private final ObjectMapper mapper;
    private final String token;

    public EvaluationPublicationController(ContentRepository repository, ObjectMapper mapper,
            @Value("${SAVEON_EVALUATION_PUBLISH_TOKEN:}") String token) {
        this.repository = repository;
        this.mapper = mapper;
        this.token = token;
    }

    private void authorize(String supplied) {
        if (token.isBlank()) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "평가 반영 기능이 설정되지 않았습니다.");
        }
        if (!MessageDigest.isEqual(token.getBytes(StandardCharsets.UTF_8),
                supplied.getBytes(StandardCharsets.UTF_8))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
    }

    private static boolean sameVideo(String first, String second) {
        var reel = REEL.matcher(first);
        if (reel.matches()) {
            var saved = REEL.matcher(second);
            return saved.matches() && reel.group(1).equals(saved.group(1));
        }
        String key = ContentSourceIdentity.key(first, null);
        return key.startsWith("youtube:") && key.equals(ContentSourceIdentity.key(second, null));
    }

    private static boolean canApply(Content content) {
        return content.getStatus() == ContentStatus.COMPLETED
                && content.getAnalyzedAt() != null && !content.isUserEdited();
    }

    record Candidate(Long id, String title, LocalDateTime analyzedAt) {}

    @GetMapping
    public List<Candidate> candidates(@RequestHeader("X-Evaluation-Token") String supplied,
            @RequestParam String sourceUrl) {
        authorize(supplied);
        return repository.findAll().stream()
                .filter(content -> canApply(content) && sameVideo(sourceUrl, content.getSourceUrl()))
                .sorted(Comparator.comparing(Content::getId).reversed())
                .map(content -> new Candidate(content.getId(), content.getTitle(), content.getAnalyzedAt()))
                .toList();
    }

    record Publication(
            @NotBlank @Size(max = 2048) String sourceUrl,
            @NotBlank @Size(max = 4000) String summary,
            @NotNull LocalDateTime expectedAnalyzedAt,
            @NotNull ObjectNode structured) {}

    @PutMapping("/{id}")
    public Candidate apply(@RequestHeader("X-Evaluation-Token") String supplied, @PathVariable Long id,
            @Valid @RequestBody Publication request) {
        authorize(supplied);
        Content content = repository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        if (!sameVideo(request.sourceUrl(), content.getSourceUrl())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "선택한 영상의 원본이 다릅니다.");
        }
        if (!canApply(content) || !request.expectedAnalyzedAt().equals(content.getAnalyzedAt())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "보관함 내용이 변경되었습니다. 새로고침 후 다시 확인하세요.");
        }
        var existing = content.getStructuredAnalysis() == null
                ? null : mapper.readTree(content.getStructuredAnalysis());
        ObjectNode merged = existing instanceof ObjectNode object ? object : mapper.createObjectNode();
        for (String field : SUMMARY_FIELDS) {
            merged.remove(field);
            if (request.structured().has(field)) merged.set(field, request.structured().get(field));
        }
        var appliedAt = LocalDateTime.now();
        int count = repository.applyEvaluationSummary(id, ContentStatus.COMPLETED,
                request.summary(), mapper.writeValueAsString(merged), request.expectedAnalyzedAt(), appliedAt);
        if (count != 1) throw new ResponseStatusException(HttpStatus.CONFLICT, "반영 전에 보관함 내용이 변경되었습니다.");
        return new Candidate(id, content.getTitle(), appliedAt);
    }
}
