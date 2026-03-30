package com.example.demo.repository;

import com.example.demo.model.Reminder;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface ReminderRepository extends JpaRepository<Reminder, UUID> {
}