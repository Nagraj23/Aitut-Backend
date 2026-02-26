package com.example.demo.service;

import com.example.demo.dto.*;
import com.example.demo.model.Users;
import com.example.demo.repository.UsersRepo;
import com.example.demo.security.JWTService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UsersRepo repo;
    private final PasswordEncoder encoder;
     private final JWTService jwtService; // Uncomment when your JWT service is ready
     private final EmailService emailService; // Uncomment when your Email service is ready

    // Using ConcurrentHashMap for better thread safety in a web app
    private final Map<String, String> otpStore = new ConcurrentHashMap<>();
    private final Map<String, Long> otpExpiry = new ConcurrentHashMap<>();

    private static final long OTP_EXPIRY_MS = 2 * 60 * 1000; // 2 minutes

    // 🎓 REGISTER (Ai-Tut Version)
    public String register(RegisterRequest req) {
        if (repo.existsByEmail(req.getEmail())) {
            throw new RuntimeException("Email already registered in Ai-Tut! 🎓");
        }

        // Using the Builder pattern we discussed earlier
        Users user = Users.builder()
                .name(req.getName())
                .email(req.getEmail())
                .password(encoder.encode(req.getPassword()))
                .role(Users.Role.valueOf(String.valueOf(req.getRole())))// STUDENT, TEACHER, or ADMIN
                .verified(false)     // Initial state
                .build();

        repo.save(user);

        // OTP Generation logic
        String otp = String.format("%06d", new Random().nextInt(999999));
        otpStore.put(req.getEmail(), otp);
        otpExpiry.put(req.getEmail(), System.currentTimeMillis() + OTP_EXPIRY_MS);

        System.out.println("🔐 [Ai-Tut] OTP for " + req.getEmail() + " is: " + otp);

        // Update this line in AuthService.java
        emailService.sendOtpEmail(user.getEmail(), "Ai-Tut Verification", user.getName(), otp);// Send the actual email here

        return "Registration successful! Check your email for the Ai-Tut verification code. 📩";
    }

    // ✅ VERIFY OTP
    public String verifyOtp(String email, String otpInput) {
        String storedOtp = otpStore.get(email);
        Long expiry = otpExpiry.get(email);

        if (storedOtp == null || expiry == null || System.currentTimeMillis() > expiry) {
            otpStore.remove(email);
            otpExpiry.remove(email);
            return "OTP expired or not found. Please request a new one. ⏰";
        }

        if (!storedOtp.equals(otpInput)) {
            return "Invalid verification code. ❌";
        }

        Users user = repo.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found 😵"));

        user.setVerified(true);
        repo.save(user);

        // Clean up store
        otpStore.remove(email);
        otpExpiry.remove(email);

        return "Account verified! Welcome to the Ai-Tut community. 🚀";
    }

    // 🔑 LOGIN
    public AuthResponse login(LoginRequest req) {
        Users user = repo.findByEmail(req.getEmail())
                .orElseThrow(() -> new RuntimeException("Invalid credentials ❌"));

        if (!user.isVerified()) {
            throw new RuntimeException("Please verify your email before logging in. ⚠️");
        }

        if (!encoder.matches(req.getPassword(), user.getPassword())) {
            throw new RuntimeException("Invalid credentials ❌");
        }

        // 1. Generate the real token
        String token = jwtService.generateToken(user.getEmail(),user.getId());

        // 2. Convert UUID and Enum to String to match your AuthResponse DTO
        return new AuthResponse(
                token,
                user.getId().toString(), // Convert UUID to String
                user.getName(),
                user.getRole().toString() // Convert Enum to String
        );
    }
    // ⚒️ UPDATE PROFILE
    public String updateProfile(UUID userId, UpdateProfileDTO dto) {

        Users user = repo.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found 💀"));

        user.setName(dto.getName());
        user.setPhoneNo(dto.getPhoneNo());
        user.setGender(dto.getGender());
        user.setDateOfBirth(dto.getDateOfBirth());
        user.setBloodGroup(dto.getBloodGroup());
        user.setProfilePicUrl(dto.getProfilePicUrl());
        user.setCollege(dto.getCollege());
        user.setDepartment(dto.getDepartment());
        user.setSpecialization(dto.getSpecialization());

        repo.save(user);

        return "Profile updated successfully ✨";
    }

    // 🔍 GET USER BY ID
    public Users getUserById(UUID id) {
        System.out.println("🔍 [GET USER] START | ID: " + id);

        return repo.findById(id)
                .orElseThrow(() -> new RuntimeException("User not found 😵"));
    }

    // 🔥 FORGOT PASSWORD
    public String forgotPassword(String email) {
        Users user = repo.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found 💀"));

        String otp = String.format("%06d", new Random().nextInt(999999));
        otpStore.put(email, otp);
        otpExpiry.put(email, System.currentTimeMillis() + OTP_EXPIRY_MS);

         emailService.sendOtpEmail(email, "Ai-Tut Password Reset", user.getName(), otp);

        System.out.println("🔐 [FORGOT PASSWORD] OTP for " + email + " is: " + otp);
        return "OTP sent for password reset 🔥";
    }

    // 🔓 RESET PASSWORD
    public String resetPassword(ResetPasswordDTO dto) {
        Users user = repo.findByEmail(dto.getEmail())
                .orElseThrow(() -> new RuntimeException("User not found"));

        user.setPassword(encoder.encode(dto.getNewPassword()));
        repo.save(user);

        return "Password reset successful 🔓";
    }
}