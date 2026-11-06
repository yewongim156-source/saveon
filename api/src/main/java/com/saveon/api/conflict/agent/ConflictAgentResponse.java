package com.saveon.api.conflict.agent;

import java.util.List;

public record ConflictAgentResponse(
        List<ConflictAgentItem> conflicts
) {
}
