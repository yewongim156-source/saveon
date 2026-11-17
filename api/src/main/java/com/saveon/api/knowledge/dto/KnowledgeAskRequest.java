package com.saveon.api.knowledge.dto;

public record KnowledgeAskRequest(
        String question,
        Integer limit
) {
}
