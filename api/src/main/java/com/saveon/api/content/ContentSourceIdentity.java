package com.saveon.api.content;

import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * Identifies one source video independently of tracking parameters.
 * A YouTube watch URL's `v` parameter IS the video identity, not tracking.
 */
public final class ContentSourceIdentity {

    private ContentSourceIdentity() { }

    public static String key(String sourceUrl, Long contentId) {
        String url = sourceUrl == null ? "" : sourceUrl.trim();
        if (url.isBlank() || url.toLowerCase(Locale.ROOT).startsWith("upload://")) {
            return "id:" + contentId;
        }

        try {
            URI uri = URI.create(url);
            String host = uri.getHost() == null
                    ? "" : uri.getHost().toLowerCase(Locale.ROOT);
            if (host.startsWith("www.")) {
                host = host.substring(4);
            }
            if (host.equals("m.youtube.com") || host.equals("music.youtube.com")) {
                host = "youtube.com";
            }

            String path = uri.getPath() == null ? "" : uri.getPath();
            if (host.equals("youtu.be")) {
                String videoId = firstPathSegment(path);
                if (!videoId.isBlank()) {
                    return "youtube:" + videoId;
                }
            }

            if (host.equals("youtube.com") || host.equals("youtube-nocookie.com")) {
                if (path.equals("/watch") || path.equals("/watch/")) {
                    String videoId = queryParameter(uri.getRawQuery(), "v");
                    // Missing video ID: do not merge all /watch links together.
                    return videoId.isBlank() ? "id:" + contentId : "youtube:" + videoId;
                }
                for (String prefix : new String[] {"/shorts/", "/live/", "/embed/"}) {
                    if (path.startsWith(prefix)) {
                        String videoId = firstPathSegment(path.substring(prefix.length()));
                        if (!videoId.isBlank()) {
                            return "youtube:" + videoId;
                        }
                    }
                }
            }
        } catch (IllegalArgumentException ignored) {
            // Preserve the original behavior for malformed and unsupported URLs.
        }

        // Instagram/Reels tracking query parameters do not identify a new video.
        // Keep the previous normalization behavior for other providers.
        String normalized = url.split("[?#]", 2)[0]
                .replaceAll("/+$", "")
                .toLowerCase(Locale.ROOT);
        return normalized.isBlank() ? "id:" + contentId : normalized;
    }

    private static String firstPathSegment(String path) {
        String cleaned = path == null ? "" : path.replaceFirst("^/+", "");
        int slash = cleaned.indexOf('/');
        return slash < 0 ? cleaned : cleaned.substring(0, slash);
    }

    private static String queryParameter(String query, String parameter) {
        if (query == null || query.isBlank()) {
            return "";
        }
        for (String part : query.split("&")) {
            String[] pair = part.split("=", 2);
            if (pair.length != 2 || !parameter.equals(pair[0])) {
                continue;
            }
            try {
                return URLDecoder.decode(pair[1], StandardCharsets.UTF_8).trim();
            } catch (IllegalArgumentException invalidEncoding) {
                return "";
            }
        }
        return "";
    }
}
