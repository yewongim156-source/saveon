package com.saveon.api.quality.correction;

import com.saveon.api.content.Content;
import com.saveon.api.quality.correction.dto.ActionCorrectionRequest;
import com.saveon.api.quality.correction.dto.ContentCorrectionRequest;
import com.saveon.api.quality.correction.dto.CorrectionStatsResponse;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/ai-corrections")
@CrossOrigin(origins = "*")
public class ContentCorrectionController {

    private final ContentCorrectionService service;

    public ContentCorrectionController(
            ContentCorrectionService service
    ) {
        this.service = service;
    }


    @PostMapping("/content/{id}")
    public Content correctContent(
            @PathVariable
            Long id,
            @RequestBody
            ContentCorrectionRequest request
    ) {
        return service.correctContent(
                id,
                request
        );
    }


    @PostMapping("/action")
    public void logActionCorrection(
            @RequestBody
            ActionCorrectionRequest request
    ) {
        service.logActionCorrection(
                request
        );
    }


    @GetMapping("/content/{id}")
    public List<AiCorrection> history(
            @PathVariable
            Long id
    ) {
        return service.history(id);
    }


    @GetMapping("/stats")
    public CorrectionStatsResponse stats() {
        return service.stats();
    }
}
