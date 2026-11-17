package com.saveon.api.interest;

import java.util.List;

public record AiInterestSynthesisResponse(
        String summary,
        List<String> keyInterests,
        List<String> takeaways
) {
}
