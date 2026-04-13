package com.example.demo.repository;

import com.example.demo.model.Users;
import com.example.demo.model.VerificationToken;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface VerificationTokenRepository extends JpaRepository<VerificationToken, Long> {
    void deleteByUser(Users user);

    Optional<VerificationToken> findByToken(String token);
}