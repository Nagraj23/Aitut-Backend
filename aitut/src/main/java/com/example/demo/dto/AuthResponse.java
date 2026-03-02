package com.example.demo.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class AuthResponse {
    private String accessToken;  // The short JWT
    private String refreshToken;
    private String id;   // This will hold the UUID as a String
    private String name;
    private String role;
}