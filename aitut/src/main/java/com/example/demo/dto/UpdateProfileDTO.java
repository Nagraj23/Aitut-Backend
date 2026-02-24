package com.example.demo.dto;

import lombok.*;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UpdateProfileDTO {

    private String name;
    private String phoneNo;

    private String gender;
    private LocalDate dateOfBirth;
    private String bloodGroup;
    private String profilePicUrl;

    private String college;
    private String department;
    private String specialization;
}