package com.example.demo.repository;

import com.example.demo.model.Users;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface UsersRepo extends JpaRepository<Users, UUID> {

    Optional<Users> findByEmail(String email);

    boolean existsByEmail(String email);
}

