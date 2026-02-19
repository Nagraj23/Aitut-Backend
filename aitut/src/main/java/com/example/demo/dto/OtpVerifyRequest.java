package com.example.demo.dto;

import lombok.*;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class OtpVerifyRequest {
    private String email;
    private String otp;
}