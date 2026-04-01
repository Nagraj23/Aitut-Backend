package com.example.demo.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class BasicProfileDto {
    private String name;
    private String phoneNo;
    private String gender;
    private String dateOfBirth; // Or LocalDate depending on your entity
    private String profilePicUrl;
} 
