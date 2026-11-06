package com.saveon.api.knowledge.dto;

import java.util.List;

public record KnowledgeAskResponse(
        String answer,
        boolean grounded,
        List<KnowledgeSourceResponse> sources
) {
}
