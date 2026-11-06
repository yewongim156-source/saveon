package com.saveon.api.reminder;

import com.saveon.api.reminder.dto.SmartReminderResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/smart-reminders")
public class SmartReminderController {

    private final SmartReminderService smartReminderService;

    public SmartReminderController(SmartReminderService smartReminderService) {
        this.smartReminderService = smartReminderService;
    }

    @GetMapping
    public List<SmartReminderResponse> getSmartReminders(
            @RequestParam(defaultValue = "6") int limit
    ) {
        int safeLimit = Math.max(1, Math.min(limit, 12));
        return smartReminderService.getReminders(safeLimit);
    }
}
