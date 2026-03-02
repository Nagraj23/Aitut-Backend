package com.example.demo.service;

import com.example.demo.model.RefreshToken;
import com.example.demo.repository.RefreshRepo;
import com.example.demo.repository.UsersRepo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Optional;
import java.util.UUID;

@Service
public class RefreshTokenService {

    @Autowired
    private RefreshRepo refreshtokenRepository;

    @Autowired
    private UsersRepo userRepository;

    /**
     * Updated logic: We pass both username AND userId.
     * We save the userId to Redis so the refresh endpoint knows who the user is
     * without hitting the PostgreSQL database again.
     */
    public RefreshToken createRefreshtoken(String username, UUID userId) {
        // 1. Create a new token object
        RefreshToken refreshToken = new RefreshToken();

        // 2. Set the owner, the user ID, and a unique UUID for the token
        refreshToken.setUsername(username);
        refreshToken.setUserId(userId); // 👈 Critical: Save ID to Redis
        refreshToken.setToken(UUID.randomUUID().toString());

        // 3. Set expiry for 30 days (Instagram style longevity)
        refreshToken.setExpiryDate(Instant.now().plus(30, ChronoUnit.DAYS));

        // 4. Save to Redis
        return refreshtokenRepository.save(refreshToken);
    }

    public Optional<RefreshToken> findByToken(String token) {
        return refreshtokenRepository.findById(token);
    }

    /**
     * Checks if the token is still valid.
     * If expired, it deletes it from Redis to keep the cache clean.
     */
    public RefreshToken verifyExpiration(RefreshToken token) {
        if (token.getExpiryDate().isBefore(Instant.now())) {
            refreshtokenRepository.delete(token);
            throw new RuntimeException("Refresh token was expired. Please make a new signin request");
        }
        return token;
    }

    /**
     * Useful for logout - deletes the token so it can't be used again.
     */
    public void deleteByToken(String token) {
        refreshtokenRepository.deleteById(token);
    }
}