package com.example.demo.model;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.security.PrivateKey;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

@Entity
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Users implements UserDetails {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(unique = true, nullable = false)
    private String email;

    @Column(nullable = false)
    private String password;

    private String name;
    private String phoneNo;

    private boolean isComplete = false;

    // Profile Fields
    private String gender;
    private LocalDate dateOfBirth;
    private String bloodGroup;
    private String profilePicUrl;

    // Academic Fields (only meaningful for STUDENT / TEACHER)
    private String college;
    private String department;
    private String University;
    private String specialization;
    private String TargetCourse;
    private String CourseDuration; 
    private Integer DailyStudyHours;

    

    @Enumerated(EnumType.STRING)
    private Role role;

    private boolean verified;

    public enum Role { STUDENT, TEACHER, INDIVIDUAL , ADMIN }

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
    }

    // --- Spring Security Stuff ---
    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.name()));
    }

    @Override
    public String getUsername() { return email; }

    @Override
    public boolean isAccountNonExpired() { return true; }

    @Override
    public boolean isAccountNonLocked() { return true; }

    @Override
    public boolean isCredentialsNonExpired() { return true; }

    @Override
    public boolean isEnabled() { return verified; }
}