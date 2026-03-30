package com.example.demo.model;

import lombok.*;
import org.springframework.data.annotation.Id; // Correct ID for Redis
import org.springframework.data.redis.core.RedisHash;
import org.springframework.data.redis.core.index.Indexed;
import java.time.Instant;
import java.util.UUID;

@Data
@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
@RedisHash(value = "RefreshToken", timeToLive = 2592000L)
public class RefreshToken {

    @Id
    private String token; // This will be the Redis Key

    @Indexed
    private String username; // Indexed allows you to find tokens by user

    private UUID UserId;
    private Instant expiryDate;

}