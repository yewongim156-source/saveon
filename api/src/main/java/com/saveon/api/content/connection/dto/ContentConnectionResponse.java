package com.saveon.api.content.connection.dto;

public record ContentConnectionResponse(
        String entity,
        String type,
        long count,
        double confidence
) {
}
