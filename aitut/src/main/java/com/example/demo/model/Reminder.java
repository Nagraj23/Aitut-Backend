package com.example.demo.model;

import com.google.api.client.util.DateTime;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import lombok.Data;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;
import java.util.UUID;

//import java.util.UUID;
@Entity
@Data
public class Reminder {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    private String topic;

    // Use Java 8 Time API for better compatibility with DBs and JSON
    private LocalDateTime triggerTime;

    // Logic: Helps the Python service filter or handle state
    private String status = "PENDING";

    private String userId;
}
