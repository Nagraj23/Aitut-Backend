package com.example.demo.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class LearningPathDTO {
    // These are validated in the Service layer based on Role
    private String college;
    private String university;
    private String department;

    @NotBlank(message = "Target course is required")
    private String currentLearning;

    @NotBlank(message = "Course duration is required")
    private String courseDuration;

    @Min(value = 1, message = "Daily study hours must be at least 1")
    @Max(value = 24, message = "Daily study hours cannot exceed 24")
    private Integer dailyStudyHours; 
}