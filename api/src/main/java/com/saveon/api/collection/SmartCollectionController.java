package com.saveon.api.collection;

import com.saveon.api.collection.dto.SmartCollectionResponse;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/smart-collections")
@CrossOrigin(origins = "*")
public class SmartCollectionController {

    private final SmartCollectionService service;

    public SmartCollectionController(
            SmartCollectionService service
    ) {
        this.service = service;
    }

    @GetMapping
    public List<SmartCollectionResponse> findCollections(
            @RequestParam(
                    name = "limit",
                    required = false
            )
            Integer limit
    ) {
        return service.findCollections(limit);
    }
}
