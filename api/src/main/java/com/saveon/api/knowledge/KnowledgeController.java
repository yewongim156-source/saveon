package com.saveon.api.knowledge;

import com.saveon.api.knowledge.dto.KnowledgeAskRequest;
import com.saveon.api.knowledge.dto.KnowledgeAskResponse;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/knowledge")
@CrossOrigin(origins = "*")
public class KnowledgeController {

    private final KnowledgeService knowledgeService;

    public KnowledgeController(
            KnowledgeService knowledgeService
    ) {
        this.knowledgeService = knowledgeService;
    }

    @PostMapping("/ask")
    public KnowledgeAskResponse ask(
            @RequestBody
            KnowledgeAskRequest request
    ) {
        return knowledgeService.ask(
                request.question(),
                request.limit()
        );
    }
}
