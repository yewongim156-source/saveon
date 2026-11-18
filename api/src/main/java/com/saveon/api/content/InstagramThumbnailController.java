package com.saveon.api.content;

import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;

/** Serves locally stored JPEGs, without exposing the private MinIO bucket. */
@RestController
@RequestMapping("/api/v1/contents")
public class InstagramThumbnailController {
    private final ContentRepository contents;
    private final InstagramThumbnailStorage storage;

    public InstagramThumbnailController(
            ContentRepository contents, InstagramThumbnailStorage storage
    ) {
        this.contents = contents;
        this.storage = storage;
    }

    @GetMapping(value = "/{id}/thumbnail", produces = MediaType.IMAGE_JPEG_VALUE)
    public ResponseEntity<byte[]> read(@PathVariable Long id) {
        if (id == null || id <= 0) return ResponseEntity.notFound().build();
        var content = contents.findById(id);
        if (content.isEmpty() || !content.get().isThumbnailAvailable()) {
            return ResponseEntity.notFound().build();
        }
        try {
            byte[] jpeg = storage.read(content.get().storedThumbnailKey());
            if (jpeg.length == 0 || jpeg.length > 180_000) {
                return ResponseEntity.notFound().build();
            }
            return ResponseEntity.ok()
                    .contentType(MediaType.IMAGE_JPEG)
                    .cacheControl(CacheControl.maxAge(Duration.ofMinutes(30)).cachePrivate())
                    .body(jpeg);
        } catch (Exception unavailable) {
            // The client has a fallback icon; never turn failed storage into a failed content.
            return ResponseEntity.notFound().build();
        }
    }
}
