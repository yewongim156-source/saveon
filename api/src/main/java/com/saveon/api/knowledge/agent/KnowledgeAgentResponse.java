package com.saveon.api.knowledge.agent;

import java.util.List;

public record KnowledgeAgentResponse(
        String answer,
        List<Long> citedContentIds
) {
}
