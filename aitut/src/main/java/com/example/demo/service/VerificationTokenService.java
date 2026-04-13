package com.example.demo.service;

import com.example.demo.model.Users;
import com.example.demo.model.VerificationToken;
import com.example.demo.repository.VerificationTokenRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class VerificationTokenService {

    private final VerificationTokenRepository tokenRepository;

    @Transactional
    public void createToken(Users user, String token) {
        // Remove any existing tokens for this user to avoid duplication
        tokenRepository.deleteByUser(user);

        VerificationToken verificationToken = new VerificationToken(token, user);
        tokenRepository.save(verificationToken);
    }

    public Optional<VerificationToken> validateToken(String token) {
        Optional<VerificationToken> vToken = tokenRepository.findByToken(token);

        if (vToken.isPresent() && vToken.get().getExpiryDate().isAfter(LocalDateTime.now())) {
            return vToken;
        }
        return Optional.empty();
    }

    @Transactional
    public void deleteToken(VerificationToken token) {
        tokenRepository.delete(token);
    }
}