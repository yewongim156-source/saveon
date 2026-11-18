package com.saveon.api.content.action;

import com.saveon.api.content.action.dto.ContentActionPlanResponse;
import com.saveon.api.content.connection.dto.ContentBundleResponse;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/content-actions")
@CrossOrigin(origins = "*")
public class ContentActionController {

    private final ContentActionService contentActionService;

    public ContentActionController(
            ContentActionService contentActionService
    ) {
        this.contentActionService =
                contentActionService;
    }


    @PostMapping("/plan")
    public ContentActionPlanResponse plan(
            @RequestBody
            ContentBundleResponse bundle
    ) {
        return contentActionService.plan(
                bundle
        );
    }


    @PostMapping("/plan/content/{id}")
    public ContentActionPlanResponse planSingleContent(
            @PathVariable
            Long id
    ) {
        return contentActionService
                .planSingleContent(id);
    }
}
