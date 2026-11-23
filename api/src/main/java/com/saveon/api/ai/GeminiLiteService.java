package com.saveon.api.ai;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Semaphore;

/** Gemini analysis for the evaluation deployment using an unbilled project. */
@Service
public class GeminiLiteService {

    private static final ZoneId EVALUATION_ZONE = ZoneId.of("Asia/Seoul");
    private static final String INTERACTIONS_URL =
            "https://generativelanguage.googleapis.com/v1beta/interactions";
    private static final String EMBEDDINGS_URL =
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent";

    private static final String VIDEO_PROMPT = """
            이 짧은 영상을 실제로 보고 들은 내용에만 근거해 한국어 JSON을 작성하세요.
            반드시 유효한 JSON 객체만 반환하며 마크다운/코드펜스는 사용하지 마세요.
            다음 형식:
            {
              "title": "짧고 구체적인 한국어 제목",
              "summary": "2~3문장 요약",
              "categories": ["쇼핑" 또는 "맛집" 또는 "여행" 또는 "레시피" 또는 "기타"],
              "keywords": ["구체적인 검색어"],
              "entities": ["영상에 실제로 나온 제품명, 브랜드명, 장소명"],
              "structured": {
                "contentType": "SHOPPING/PLACE/RECIPE/GENERAL",
                "facts": [
                  {"field": "가격/날짜/주소/제품명 등", "value": "확인한 내용", "evidenceText": "확인 가능한 실제 발화나 화면 글자"}
                ]
              }
            }
            중요한 조건:
            - 확인되지 않은 가격, 위치, 이름, 날짜를 추측하지 마세요.
            - 근거 문장이 식별되지 않는 경우 evidenceText를 빈 문자열로 하세요.
            - 외부 사실 검증이 이루어진 것처럼 주장하지 마세요.
            - 언급되지 않은 항목은 빈 배열이나 빈 문자열로 작성하세요.
            - 최대 키워드 10개, 엔티티 10개, facts 12개로 제한하세요.
            """;

    private final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10)).build();
    private final JsonMapper mapper = JsonMapper.builder().build();
    private final String apiKey;
    private final String model;
    private final int maxDailyAnalyses;
    private final Semaphore analysisSlots = new Semaphore(1);
    private LocalDate trackedDay = LocalDate.now(EVALUATION_ZONE);
    private int analysesToday = 0;

    public GeminiLiteService(
            @Value("${GEMINI_API_KEY:}") String apiKey,
            @Value("${SAVEON_LITE_MODEL:gemini-3.5-flash-lite}") String model,
            @Value("${SAVEON_LITE_DAILY_ANALYSES:20}") int maxDailyAnalyses
    ) {
        this.apiKey = apiKey.strip();
        this.model = model.strip();
        this.maxDailyAnalyses = Math.max(0, Math.min(maxDailyAnalyses, 100));
    }

    public AiAnalyzeResponse analyzeLink(String sourceUrl) {
        String reelUrl = InstagramReelMedia.canonicalUrl(sourceUrl);
        if (reelUrl == null) {
            return analyzeYouTube(sourceUrl);
        }
        return analyzeVideo(() -> Map.of(
                "type", "video",
                "mime_type", "video/mp4",
                "data", Base64.getEncoder().encodeToString(InstagramReelMedia.download(reelUrl))
        ), "GEMINI_INSTAGRAM_EVALUATION");
    }

    public AiAnalyzeResponse analyzeYouTube(String sourceUrl) {
        validateYouTubeUrl(sourceUrl);
        return analyzeVideo(() -> Map.of("type", "video", "uri", sourceUrl),
                "GEMINI_YOUTUBE_EVALUATION");
    }

    private AiAnalyzeResponse analyzeVideo(
            java.util.function.Supplier<Map<String, Object>> videoInput, String method
    ) {
        ensureKey();
        if (!analysisSlots.tryAcquire()) {
            throw new IllegalStateException("다른 영상을 분석 중입니다. 잠시 후 다시 시도해 주세요.");
        }
        try {
            consumeDailyAnalysisQuota();
            Map<String, Object> request = Map.of(
                    "model", model,
                    "store", false,
                    "input", List.of(
                            videoInput.get(),
                            Map.of("type", "text", "text", VIDEO_PROMPT)
                    )
            );
            Map<String, Object> result = callJson(INTERACTIONS_URL, request,
                    Duration.ofSeconds(150));
            String output = extractModelText(result);
            String jsonText = extractJson(output);
            Map<String, Object> parsed = mapper.readValue(jsonText, Map.class);

            String title = fieldText(parsed.get("title"), "저장한 영상");
            String summary = fieldText(parsed.get("summary"), "");
            if (summary.isBlank()) {
                throw new IllegalStateException("영상 요약이 비어 있습니다.");
            }
            List<String> categories = strings(parsed.get("categories"), 4);
            List<String> keywords = strings(parsed.get("keywords"), 10);
            List<String> entities = strings(parsed.get("entities"), 10);
            Map<String, Object> structured = new LinkedHashMap<>();
            if (parsed.get("structured") instanceof Map<?, ?> details) {
                details.forEach((key, value) -> {
                    if (key instanceof String name) structured.put(name, value);
                });
            }
            structured.put("analysisMethod", method);
            structured.put("externalFactCheckPerformed", false);
            structured.put("evidenceSource", "Gemini video understanding");
            return new AiAnalyzeResponse(
                    title, summary, categories, keywords, entities, structured, null);
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("영상 분석을 완료하지 못했습니다.", e);
        } finally {
            analysisSlots.release();
        }
    }

    public AiEmbedResponse embed(String content) {
        ensureKey();
        if (content == null || content.isBlank()) {
            throw new IllegalArgumentException("임베딩할 텍스트가 없습니다.");
        }
        String text = content.length() > 5000 ? content.substring(0, 5000) : content;
        Map<String, Object> request = Map.of(
                "model", "models/gemini-embedding-001",
                "content", Map.of("parts", List.of(Map.of("text", text))),
                "outputDimensionality", 768
        );
        Map<String, Object> payload = callJson(EMBEDDINGS_URL, request,
                Duration.ofSeconds(45));
        if (!(payload.get("embedding") instanceof Map<?, ?> embedded)
                || !(embedded.get("values") instanceof List<?> values)
                || values.size() != 768) {
            throw new IllegalStateException("Gemini 임베딩 응답이 768차원이 아닙니다.");
        }
        List<Float> vector = new ArrayList<>(768);
        double magnitude = 0;
        for (Object value : values) {
            if (!(value instanceof Number number)) {
                throw new IllegalStateException("임베딩 응답에 숫자가 아닌 값이 있습니다.");
            }
            float v = number.floatValue();
            magnitude += (double) v * v;
            vector.add(v);
        }
        if (magnitude <= 0) throw new IllegalStateException("빈 임베딩 벡터");
        float norm = (float) Math.sqrt(magnitude);
        vector.replaceAll(x -> x / norm);
        return new AiEmbedResponse("gemini-embedding-001", 768, vector);
    }

    private void ensureKey() {
        if (apiKey.isEmpty()) {
            throw new IllegalStateException(
                    "무료 Gemini API 키가 Render 환경변수에 설정되지 않았습니다.");
        }
    }

    private synchronized void consumeDailyAnalysisQuota() {
        LocalDate today = LocalDate.now(EVALUATION_ZONE);
        if (!today.equals(trackedDay)) {
            trackedDay = today;
            analysesToday = 0;
        }
        if (analysesToday >= maxDailyAnalyses) {
            throw new IllegalStateException(
                    "평가판의 오늘 영상 분석 횟수를 모두 사용했습니다.");
        }
        analysesToday++;
    }

    private void validateYouTubeUrl(String sourceUrl) {
        try {
            URI uri = URI.create(sourceUrl);
            String host = uri.getHost();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null
                    || !(host.equals("youtube.com") || host.endsWith(".youtube.com")
                       || host.equals("youtu.be"))) {
                throw new IllegalArgumentException(
                        "무료 웹 평가판은 공개 YouTube 링크 분석만 지원합니다.");
            }
            String path = uri.getPath() == null ? "" : uri.getPath();
            if (!(path.startsWith("/shorts/") || path.equals("/watch")
                    || host.equals("youtu.be"))) {
                throw new IllegalArgumentException("YouTube 영상 링크를 입력해 주세요.");
            }
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException(
                    "무료 웹 평가판은 공개 YouTube 쇼츠 링크만 분석할 수 있습니다.",
                    exception);
        }
    }

    private Map<String, Object> callJson(
            String url, Map<String, Object> requestBody, Duration timeout) {
        try {
            String body = mapper.writeValueAsString(requestBody);
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(timeout)
                    .header("Content-Type", "application/json")
                    .header("x-goog-api-key", apiKey)
                    .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> response = client.send(request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException(
                        "Gemini 응답 오류 HTTP " + response.statusCode()
                        + " (무료 할당량·모델 접근권한을 확인해 주세요.)");
            }
            return mapper.readValue(response.body(), Map.class);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("AI 요청이 중단됐습니다.", e);
        } catch (HttpTimeoutException e) {
            throw new IllegalStateException("Gemini API 응답 시간이 초과됐습니다.", e);
        } catch (IOException e) {
            throw new IllegalStateException("Gemini API 연결 오류: " + e.getClass().getSimpleName(), e);
        }
    }

    private static String extractModelText(Map<String, Object> result) {
        Object steps = result.get("steps");
        StringBuilder builder = new StringBuilder();
        if (steps instanceof List<?> list) {
            for (Object item : list) {
                if (!(item instanceof Map<?, ?> step)
                        || !"model_output".equals(step.get("type"))
                        || !(step.get("content") instanceof List<?> content)) continue;
                for (Object block : content) {
                    if (block instanceof Map<?, ?> textItem
                            && "text".equals(textItem.get("type"))
                            && textItem.get("text") instanceof String value) {
                        builder.append(value);
                    }
                }
            }
        }
        if (builder.isEmpty()) {
            throw new IllegalStateException("Gemini 영상 분석 결과가 비어 있습니다.");
        }
        return builder.toString();
    }

    private static String extractJson(String value) {
        int start = value.indexOf('{');
        int end = value.lastIndexOf('}');
        if (start < 0 || end <= start) {
            throw new IllegalStateException("Gemini가 JSON으로 응답하지 않았습니다.");
        }
        return value.substring(start, end + 1);
    }

    private static String fieldText(Object value, String fallback) {
        return value instanceof String text && !text.isBlank()
                ? text.strip() : fallback;
    }

    private static List<String> strings(Object value, int limit) {
        if (!(value instanceof List<?> values)) return List.of();
        List<String> result = new ArrayList<>();
        for (Object raw : values) {
            if (raw instanceof String s && !s.isBlank()) {
                result.add(s.strip());
                if (result.size() == limit) break;
            }
        }
        return result;
    }
}
