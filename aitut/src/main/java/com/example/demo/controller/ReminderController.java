package com.example.demo.controller;

import com.example.demo.model.Reminder;
import com.example.demo.service.ReminderService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/reminders")
public class ReminderController {

    @Autowired
    private ReminderService reminderService;

    @PostMapping
    public Reminder setReminder(@RequestBody Reminder reminder) {
        return reminderService.createReminder(reminder);
    }
}
