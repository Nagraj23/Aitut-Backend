package com.example.demo.model;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "refresh_tokens")
@Data
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class RefreshTokenEntity {

    @Id
    @Column(length = 128, nullable = false)
    private String token;

    @Column(nullable = false, length = 255)
    private String username;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "expiry_date", nullable = false)
    private Instant expiryDate;
}

