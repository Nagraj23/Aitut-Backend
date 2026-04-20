package com.example.demo.dto;

import lombok.Data;
import java.util.List;

@Data
public class BulkRequest {
    // Common Data
    private String college;
    private String university;
    private String department;
    private String courseDuration;
    // private String targetCourse;
    private String tpoId;

    // Individual Student Data
    private List<StudentBasicInfo> students;
}

