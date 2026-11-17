package com.saveon.api.action;

import java.util.List;

public record AiActionPlanResponse(
        List<AiActionItemResponse> actions
) {
}
