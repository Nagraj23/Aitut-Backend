package com.example.demo.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class LearningPathDTO {
    // Academic Info (Crucial for STUDENT role)
    private String college;
    private String university;
    private String department;

    // Course Info (Crucial for BOTH roles)
    private String targetCourse;
    private String courseDuration;
    private Integer dailyStudyHours; 
}