package com.example.demo.service;

import com.example.demo.model.Reminder;
import com.example.demo.repository.ReminderRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class ReminderService {

    @Autowired
    private ReminderRepository repository;

    @Autowired
    private StringRedisTemplate redisTemplate; // Used to send messages

    @Autowired
    private ObjectMapper objectMapper;

    public Reminder createReminder(Reminder reminder) {
        // 1. Save to DB
        Reminder savedReminder = repository.save(reminder);

        try {
            String jsonMessage = objectMapper.writeValueAsString(savedReminder);
            redisTemplate.convertAndSend("alarm_channel", jsonMessage);
        } catch (Exception e) {
            // Handle serialization error
        }

        return savedReminder;
    }
}