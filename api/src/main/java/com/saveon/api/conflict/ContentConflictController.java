package com.saveon.api.conflict;

import com.saveon.api.conflict.dto.ContentConflictResponse;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/content-conflicts")
@CrossOrigin(origins = "*")
public class ContentConflictController {

    private final ContentConflictService service;

    public ContentConflictController(
            ContentConflictService service
    ) {
        this.service = service;
    }

    @GetMapping
    public List<ContentConflictResponse> findConflicts(
            @RequestParam(
                    name = "limit",
                    required = false
            )
            Integer limit
    ) {
        return service.findConflicts(limit);
    }
}
