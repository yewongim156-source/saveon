package com.saveon.api.content.action.dto;

import java.util.List;

public record ContentActionPlanResponse(
        String source,
        List<ContentActionItemResponse> actions
) {
}
