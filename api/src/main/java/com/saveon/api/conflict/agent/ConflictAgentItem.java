package com.saveon.api.conflict.agent;

import java.util.List;

public record ConflictAgentItem(
        String subject,
        String claimType,
        String title,
        String description,
        String severity,
        List<ConflictAgentEvidence> evidences
) {
}
