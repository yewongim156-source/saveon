package com.saveon.api.content;

import com.saveon.api.content.dto.CreateContentRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/v1/contents")
@CrossOrigin(origins = "*")
public class ContentController {

    private final ContentService contentService;

    public ContentController(
            ContentService contentService
    ) {
        this.contentService = contentService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Content create(
            @Valid
            @RequestBody
            CreateContentRequest request
    ) {
        return contentService.create(request);
    }

    @PostMapping(
            value = "/upload",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE
    )
    @ResponseStatus(HttpStatus.CREATED)
    public Content uploadVideo(
            @RequestPart("file")
            MultipartFile file
    ) {
        return contentService.createFromVideo(file);
    }

    @GetMapping
    public List<Content> findAll() {
        return contentService.findAll();
    }

    @GetMapping("/{id}")
    public Content findById(
            @PathVariable Long id
    ) {
        return contentService.findById(id);
    }

    @PostMapping("/{id}/analyze")
    public Content analyze(
            @PathVariable Long id
    ) {
        return contentService.analyzeById(id);
    }
}
