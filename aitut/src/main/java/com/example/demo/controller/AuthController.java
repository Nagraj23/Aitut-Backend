package com.example.demo.controller; // Updated package

import com.example.demo.dto.*; // Ensure these DTOs exist in your project
import com.example.demo.model.Users;
import com.example.demo.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    // ✅ Register a new user (Student/Teacher)
    @PostMapping("/register")
    public ResponseEntity<String> register(@Valid @RequestBody RegisterRequest request) {
        return ResponseEntity.ok(authService.register(request));
    }

    // ✅ User login (returns JWT)
    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(@RequestBody LoginRequest request) {
        return ResponseEntity.ok(authService.login(request));
    }

    // ✅ Verify OTP for email verification
    @PostMapping("/verify-otp")
    public ResponseEntity<String> verifyOtp(@RequestBody OtpVerifyRequest otpReq) {
        String result = authService.verifyOtp(otpReq.getEmail(), otpReq.getOtp());
        return ResponseEntity.ok(result);
    }

    // ✅ Update user profile (Uses UUID for PostgreSQL)
    @PutMapping("/update-profile/{userId}")
    public ResponseEntity<String> updateProfile(@PathVariable UUID userId, @RequestBody UpdateProfileDTO dto) {
        return ResponseEntity.ok(authService.updateProfile(userId, dto));
    }

    // ✅ Get user by ID (Uses UUID)
    @GetMapping("/user/{id}")
    public ResponseEntity<Users> getUserById(@PathVariable UUID id) {
        return ResponseEntity.ok(authService.getUserById(id));
    }

    // 🔥 Forgot Password: Generate and send OTP
    @PostMapping("/forgot-password")
    public ResponseEntity<String> forgotPassword(@RequestBody ForgotPasswordRequest request) {
        return ResponseEntity.ok(authService.forgotPassword(request.getEmail()));
    }

    // 🔥 Reset Password after OTP verified
    @PostMapping("/reset-password")
    public ResponseEntity<String> resetPassword(@RequestBody ResetPasswordDTO request) {
        return ResponseEntity.ok(authService.resetPassword(request));
    }
}