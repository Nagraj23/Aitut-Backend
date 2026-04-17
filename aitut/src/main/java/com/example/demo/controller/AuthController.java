package com.example.demo.controller;

import com.example.demo.dto.*;
import com.example.demo.model.Users;
import com.example.demo.security.JWTService;
import com.example.demo.service.AuthService;
import com.example.demo.service.RefreshTokenService;
import com.example.demo.service.VerificationTokenService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor // This injects all 'final' fields automatically
public class AuthController {

    // Must be final to be injected by Lombok
    private final RefreshTokenService refreshTokenService;
    private final JWTService jwtService;
    private final AuthService authService;

    // ✅ Register a new user
    @PostMapping("/register")
    public ResponseEntity<String> register(@Valid @RequestBody RegisterRequest request) {
        return ResponseEntity.ok(authService.register(request));
    }

    // ✅ User login (Returns both Access and Refresh Tokens)
    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(@RequestBody LoginRequest request) {
        return ResponseEntity.ok(authService.login(request));
    }

    @PostMapping("/verify-otp")
    public ResponseEntity<String> verifyOtp(@RequestBody OtpVerifyRequest otpReq) {

        String result = authService.verifyOtp(
                otpReq.getEmail(),
                otpReq.getOtp(),
                otpReq.getType()
        );

        return ResponseEntity.ok(result);
    }

    @PostMapping("/tpo/invite-bulk")
    public ResponseEntity<String> inviteBulkStudents(@RequestBody BulkRequest bulkRequest) {
        authService.inviteBulkStudents(bulkRequest);
        return ResponseEntity.ok("Students added and welcome emails sent successfully!");
    }



    @PostMapping("/google-login")
    public ResponseEntity<AuthResponse> googleLogin(@RequestBody Map<String, String> request) {
        // This extracts the "token" from the JSON body
        String token = request.get("token");

        // Now this matches the 1 parameter the Service expects!
        return ResponseEntity.ok(authService.googleLogin(token));
    }
    // ✅ Update profile
 // 1. Route for Personal/Basic Details
@PutMapping("/update-profile/basic/{userId}")
    public ResponseEntity<AuthResponse> updateBasicProfile(
            @PathVariable UUID userId, 
            @Valid @RequestBody BasicProfileDto dto) { // Added @Valid
        
        AuthResponse response = authService.updateBasicInfo(userId, dto);
        return ResponseEntity.ok(response);
    }

    // 2. Route for Academic/Learning Goals
    @PutMapping("/update-profile/learning/{userId}")
    public ResponseEntity<AuthResponse> updateLearningPath(
            @PathVariable UUID userId, 
            @Valid @RequestBody LearningPathDTO dto) { // Added @Valid
        
        AuthResponse response = authService.updateLearningProfile(userId, dto);
        return ResponseEntity.ok(response);
    }

    // ✅ Get user by ID
    @GetMapping("/user/{id}")
    public ResponseEntity<Users> getUserById(@PathVariable UUID id) {
        return ResponseEntity.ok(authService.getUserById(id));
    }

    // 🔥 Forgot Password
    @PostMapping("/forgot-password")
    public ResponseEntity<String> forgotPassword(@RequestBody ForgotPasswordRequest request) {
        return ResponseEntity.ok(authService.forgotPassword(request.getEmail()));
    }

    // 🔄 REFRESH TOKEN (The "Insta-style" long session)
    @PostMapping("/refreshtoken")
    public ResponseEntity<?> refreshtoken(@RequestBody TokenRefreshRequest request) {
        String requestRefreshToken = request.getRefreshToken();

        return refreshTokenService.findByToken(requestRefreshToken)
                .map(refreshTokenService::verifyExpiration)
                .map(token -> {
                    // Pull username and userId from Redis to create a fresh JWT
                    String newAccessToken = jwtService.generateToken(token.getUsername(), token.getUserId());

                    // Return new access token with the existing refresh token
                    return ResponseEntity.ok(new TokenRefreshResponse(newAccessToken, requestRefreshToken));
                })
                .orElseThrow(() -> new RuntimeException("Refresh token is not in database or expired!"));
    }
    @PostMapping("/github")
    public ResponseEntity<AuthResponse> githubLogin(@RequestBody GithubLoginRequest request) {

        AuthResponse response = authService.githubLogin(request.getCode());
        return ResponseEntity.ok(response);
    }
    // 🔥 Reset Password
    @PostMapping("/reset-password")
    public ResponseEntity<String> resetPassword(@RequestBody ResetPasswordDTO request) {
        return ResponseEntity.ok(authService.resetPassword(request));
    }
}