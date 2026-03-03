package com.example.demo.service;

import com.example.demo.dto.*;
import com.example.demo.model.Users;
import com.example.demo.model.RefreshToken;
import com.example.demo.repository.UsersRepo;
import com.example.demo.security.JWTService;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import com.google.api.client.googleapis.auth.oauth2.GoogleIdToken;
import com.google.api.client.googleapis.auth.oauth2.GoogleIdTokenVerifier;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.json.gson.GsonFactory;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UsersRepo repo;
    private final RefreshTokenService refreshTokenService;
    private final PasswordEncoder encoder;
    private final JWTService jwtService;
    private final EmailService emailService;

    private final Map<String, Boolean> otpVerifiedForReset = new ConcurrentHashMap<>();
    private final Map<String, String> otpStore = new ConcurrentHashMap<>();
    private final Map<String, Long> otpExpiry = new ConcurrentHashMap<>();

    private static final long OTP_EXPIRY_MS = 2 * 60 * 1000;

    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${spring.security.oauth2.client.registration.github.client-id}")
    private String githubClientId;

    @Value("${spring.security.oauth2.client.registration.github.client-secret}")
    private String githubClientSecret;

    @Value("${spring.security.oauth2.client.registration.google.client-id}")
    private String googleClientId;

    // ================= REGISTER =================

    public String register(RegisterRequest req) {

        if (repo.existsByEmail(req.getEmail())) {
            throw new RuntimeException("Email already registered!");
        }

        Users user = Users.builder()
                .name(req.getName())
                .email(req.getEmail())
                .password(encoder.encode(req.getPassword()))
                .role(Users.Role.valueOf(req.getRole().name()))
                .verified(false)
                .build();

        repo.save(user);

        generateAndSendOtp(user.getEmail(), user.getName(), "Account Verification");

        return "Registration successful! Check email for verification OTP.";
    }

    // ================= VERIFY OTP =================

    public String verifyOtp(String email, String otpInput, String type) {

        if (!isOtpValid(email, otpInput)) {
            return "Invalid or expired OTP!";
        }

        if ("ACCOUNT".equalsIgnoreCase(type)) {

            Users user = repo.findByEmail(email)
                    .orElseThrow(() -> new RuntimeException("User not found"));

            user.setVerified(true);
            repo.save(user);

        } else if ("RESET".equalsIgnoreCase(type)) {

            otpVerifiedForReset.put(email, true);

        } else {
            throw new RuntimeException("Invalid OTP type");
        }

        clearOtp(email);

        return "OTP verified successfully!";
    }

    // ================= LOGIN =================

    public AuthResponse login(LoginRequest req) {

        Users user = repo.findByEmail(req.getEmail())
                .orElseThrow(() -> new RuntimeException("Invalid credentials"));

        if (!user.isVerified()) {
            throw new RuntimeException("Please verify your email first!");
        }

        if (!encoder.matches(req.getPassword(), user.getPassword())) {
            throw new RuntimeException("Invalid credentials");
        }

        return createAuthResponse(user);
    }

    // ================= GOOGLE LOGIN =================

    public AuthResponse googleLogin(String idTokenString) {

        try {
            GoogleIdTokenVerifier verifier = new GoogleIdTokenVerifier.Builder(
                    new NetHttpTransport(), new GsonFactory())
                    .setAudience(Collections.singletonList(googleClientId))
                    .build();

            GoogleIdToken idToken = verifier.verify(idTokenString);

            if (idToken == null) {
                throw new RuntimeException("Invalid Google Token");
            }

            GoogleIdToken.Payload payload = idToken.getPayload();
            String email = payload.getEmail();
            String name = (String) payload.get("name");

            Users user = repo.findByEmail(email).orElseGet(() ->
                    repo.save(Users.builder()
                            .name(name)
                            .email(email)
                            .password(encoder.encode(UUID.randomUUID().toString()))
                            .role(Users.Role.STUDENT)
                            .verified(true)
                            .build())
            );

            return createAuthResponse(user);

        } catch (Exception e) {
            throw new RuntimeException("Google Auth Failed: " + e.getMessage());
        }
    }

    // ================= GITHUB LOGIN =================

    public AuthResponse githubLogin(String code) {

        String tokenUrl = "https://github.com/login/oauth/access_token";

        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
        params.add("client_id", githubClientId);
        params.add("client_secret", githubClientSecret);
        params.add("code", code);

        HttpHeaders headers = new HttpHeaders();
        headers.setAccept(Collections.singletonList(MediaType.APPLICATION_JSON));

        HttpEntity<MultiValueMap<String, String>> request =
                new HttpEntity<>(params, headers);

        Map<String, Object> tokenResponse =
                restTemplate.postForObject(tokenUrl, request, Map.class);

        if (tokenResponse == null || tokenResponse.get("access_token") == null) {
            throw new RuntimeException("GitHub Login Failed");
        }

        String accessToken = (String) tokenResponse.get("access_token");

        String email = fetchPrimaryEmail(accessToken);
        String name = fetchGithubName(accessToken);

        Users user = repo.findByEmail(email).orElseGet(() ->
                repo.save(Users.builder()
                        .name(name)
                        .email(email)
                        .password(encoder.encode(UUID.randomUUID().toString()))
                        .role(Users.Role.STUDENT)
                        .verified(true)
                        .build())
        );

        return createAuthResponse(user);
    }

    private String fetchPrimaryEmail(String token) {

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);

        ResponseEntity<List> response = restTemplate.exchange(
                "https://api.github.com/user/emails",
                HttpMethod.GET,
                new HttpEntity<>(headers),
                List.class
        );

        List<Map<String, Object>> emails = response.getBody();

        return emails.stream()
                .filter(e -> Boolean.TRUE.equals(e.get("primary")))
                .map(e -> (String) e.get("email"))
                .findFirst()
                .orElseThrow(() -> new RuntimeException("Primary email not found"));
    }

    private String fetchGithubName(String token) {

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);

        Map profile = restTemplate.exchange(
                "https://api.github.com/user",
                HttpMethod.GET,
                new HttpEntity<>(headers),
                Map.class
        ).getBody();

        return profile.get("name") != null
                ? (String) profile.get("name")
                : (String) profile.get("login");
    }

    // ================= UPDATE PROFILE =================

    public String updateProfile(UUID userId, UpdateProfileDTO dto) {

        Users user = repo.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));

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

        return "Profile updated successfully!";
    }

    // ================= GET USER =================

    public Users getUserById(UUID id) {
        return repo.findById(id)
                .orElseThrow(() -> new RuntimeException("User not found"));
    }

    // ================= FORGOT PASSWORD =================

    public String forgotPassword(String email) {

        Users user = repo.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found"));

        generateAndSendOtp(email, user.getName(), "Password Reset");

        return "OTP sent for password reset";
    }

    // ================= RESET PASSWORD =================

    public String resetPassword(ResetPasswordDTO dto) {

        Boolean verified = otpVerifiedForReset.get(dto.getEmail());

        if (verified == null || !verified) {
            throw new RuntimeException("OTP not verified for password reset!");
        }

        Users user = repo.findByEmail(dto.getEmail())
                .orElseThrow(() -> new RuntimeException("User not found"));

        user.setPassword(encoder.encode(dto.getNewPassword()));
        repo.save(user);

        otpVerifiedForReset.remove(dto.getEmail());

        return "Password reset successful";
    }

    // ================= COMMON METHODS =================

    private AuthResponse createAuthResponse(Users user) {

        String accessToken = jwtService.generateToken(user.getEmail(), user.getId());
        RefreshToken refreshToken =
                refreshTokenService.createRefreshtoken(user.getEmail(), user.getId());

        return new AuthResponse(
                accessToken,
                refreshToken.getToken(),
                user.getId().toString(),
                user.getName(),
                user.getRole().toString()
        );
    }

    private void generateAndSendOtp(String email, String name, String subject) {

        String otp = String.format("%06d", new Random().nextInt(999999));

        otpStore.put(email, otp);
        otpExpiry.put(email, System.currentTimeMillis() + OTP_EXPIRY_MS);

        emailService.sendOtpEmail(email, subject, name, otp);
    }

    private boolean isOtpValid(String email, String otpInput) {

        String storedOtp = otpStore.get(email);
        Long expiry = otpExpiry.get(email);

        if (storedOtp == null || expiry == null || System.currentTimeMillis() > expiry) {
            clearOtp(email);
            return false;
        }

        return storedOtp.equals(otpInput);
    }

    private void clearOtp(String email) {
        otpStore.remove(email);
        otpExpiry.remove(email);
    }
}