package com.saveon.api.content.connection.dto;

public record RelatedEntityResponse(
        String entity,
        String type,
        long count
) {
}
