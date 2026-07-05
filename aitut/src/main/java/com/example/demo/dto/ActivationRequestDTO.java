package com.example.demo.dto;

import lombok.Data;

@Data
public class ActivationRequestDTO {
    private String token;
    private String password;
}