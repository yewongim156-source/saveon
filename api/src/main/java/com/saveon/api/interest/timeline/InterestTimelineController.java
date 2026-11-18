package com.saveon.api.interest.timeline;

import com.saveon.api.interest.timeline.dto.InterestTimelineResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/interest-timeline")
public class InterestTimelineController {

    private final InterestTimelineService interestTimelineService;

    public InterestTimelineController(InterestTimelineService interestTimelineService) {
        this.interestTimelineService = interestTimelineService;
    }

    @GetMapping
    public InterestTimelineResponse getInterestTimeline() {
        return interestTimelineService.getTimeline();
    }
}
