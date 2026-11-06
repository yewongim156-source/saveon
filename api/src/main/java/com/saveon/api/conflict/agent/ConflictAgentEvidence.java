package com.saveon.api.conflict.agent;

public record ConflictAgentEvidence(
        Long contentId,
        String claimText,
        String value
) {
}
