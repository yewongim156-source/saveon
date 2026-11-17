package com.saveon.api.comparison;

import com.saveon.api.comparison.dto.CollectionComparisonRequest;
import com.saveon.api.comparison.dto.CollectionComparisonResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/collection-comparisons")
public class CollectionComparisonController {

    private final CollectionComparisonService service;

    public CollectionComparisonController(
            CollectionComparisonService service
    ) {
        this.service = service;
    }

    @PostMapping
    public ResponseEntity<CollectionComparisonResponse> compare(
            @RequestBody CollectionComparisonRequest request
    ) {
        return ResponseEntity.ok(
                service.compare(request)
        );
    }
}
