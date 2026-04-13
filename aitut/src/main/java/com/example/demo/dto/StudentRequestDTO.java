package com.example.demo.dto;

import lombok.Data;

import java.util.UUID;

@Data
public class StudentRequestDTO {
    private String name;
    private String email;
    private String college;
    private String department;    // Use this for "Branch"
    private String university;
    private UUID tpoId;
    private String specialization;
    private int year;
}
