package com.saveon.api.ai;

import java.io.IOException;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;

final class InstagramReelMedia {

    private static final Pattern REEL_PATH = Pattern.compile("/reel/([A-Za-z0-9_-]{1,32})/?");
    private static final long MAX_VIDEO_BYTES = 8 * 1024 * 1024;

    private InstagramReelMedia() {
    }

    static String canonicalUrl(String sourceUrl) {
        URI uri = URI.create(sourceUrl);
        String host = uri.getHost();
        var path = REEL_PATH.matcher(uri.getRawPath() == null ? "" : uri.getRawPath());
        if (!"https".equalsIgnoreCase(uri.getScheme())
                || !("instagram.com".equalsIgnoreCase(host) || "www.instagram.com".equalsIgnoreCase(host))
                || uri.getRawUserInfo() != null || uri.getPort() != -1 || !path.matches()) {
            return null;
        }
        return "https://www.instagram.com/reel/" + path.group(1) + "/";
    }

    static byte[] download(String reelUrl) {
        try (var directory = new TemporaryMediaDirectory()) {
            Path video = directory.path.resolve("reel.mp4");
            Process downloader = new ProcessBuilder(
                    "yt-dlp", "--ignore-config", "--no-playlist", "--no-cache-dir",
                    "--socket-timeout", "12", "--retries", "0", "--fragment-retries", "0",
                    "--max-filesize", "8M", "--merge-output-format", "mp4",
                    "-f", "bv[ext=mp4][height<=720]+ba[ext=m4a]/b[ext=mp4][height<=720]",
                    "-o", video.toString(), "--", reelUrl)
                    .redirectOutput(ProcessBuilder.Redirect.DISCARD)
                    .redirectError(ProcessBuilder.Redirect.DISCARD)
                    .start();
            try {
                if (!downloader.waitFor(65, TimeUnit.SECONDS)) {
                    throw new IllegalStateException("Instagram 릴스 다운로드 시간이 초과됐습니다.");
                }
                if (downloader.exitValue() != 0 || !Files.isRegularFile(video)) {
                    throw new IllegalStateException("공개 Instagram 릴스의 영상과 음성을 가져오지 못했습니다.");
                }
                long size = Files.size(video);
                if (size == 0 || size > MAX_VIDEO_BYTES) {
                    throw new IllegalStateException("릴스 분석은 8MB 이하의 영상을 지원합니다.");
                }
                return Files.readAllBytes(video);
            } finally {
                downloader.descendants().forEach(ProcessHandle::destroyForcibly);
                downloader.destroyForcibly();
            }
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("릴스 다운로드가 중단됐습니다.", exception);
        } catch (IOException exception) {
            throw new IllegalStateException("릴스 임시 파일을 처리하지 못했습니다.", exception);
        }
    }

    private static final class TemporaryMediaDirectory implements AutoCloseable {

        private final Path path = Files.createTempDirectory("saveon-reel-");

        private TemporaryMediaDirectory() throws IOException {
        }

        @Override
        public void close() throws IOException {
            try (var files = Files.newDirectoryStream(path)) {
                for (Path file : files) {
                    Files.deleteIfExists(file);
                }
            }
            Files.deleteIfExists(path);
        }
    }
}
