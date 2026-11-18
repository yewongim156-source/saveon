package com.saveon.api.quality.canonical;

import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/canonical-entities")
@CrossOrigin(origins = "*")
public class CanonicalEntityController {

    private final CanonicalEntityService service;

    public CanonicalEntityController(
            CanonicalEntityService service
    ) {
        this.service = service;
    }


    @GetMapping
    public List<CanonicalEntity> findAll() {
        return service.findAll();
    }


    @GetMapping("/lookup")
    public CanonicalEntity lookup(
            @RequestParam
            String name
    ) {
        return service
                .find(name)
                .orElseThrow(
                        () ->
                                new IllegalArgumentException(
                                        "Canonical entity not found: "
                                                + name
                                )
                );
    }
}
