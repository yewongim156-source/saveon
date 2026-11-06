package com.saveon.api.content.connection.dto;

import java.util.List;

public record ContentInterestSynthesisResponse(
        String source,
        String summary,
        List<String> keyInterests,
        List<String> takeaways
) {
}
