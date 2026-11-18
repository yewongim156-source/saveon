package com.saveon.api.quality.validation;

import com.saveon.api.quality.validation.dto.ContentQualityResponse;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/content-quality")
@CrossOrigin(origins = "*")
public class ContentQualityController {

    private final ContentQualityService service;

    public ContentQualityController(
            ContentQualityService service
    ) {
        this.service = service;
    }


    @GetMapping("/{id}")
    public ContentQualityResponse validate(
            @PathVariable
            Long id
    ) {
        return service.validate(id);
    }
}
