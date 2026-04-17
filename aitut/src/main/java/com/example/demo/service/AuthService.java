package com.example.demo.service;

import com.example.demo.dto.*;
import com.example.demo.model.Users;
import com.example.demo.model.RefreshToken;
import com.example.demo.model.VerificationToken;
import com.example.demo.repository.UsersRepo;
import com.example.demo.security.JWTService;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
// <--- ADD THIS
import org.springframework.http.*;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import com.example.demo.repository.VerificationTokenRepository;
import com.example.demo.service.VerificationTokenService;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import com.google.api.client.googleapis.auth.oauth2.GoogleIdToken;
import com.google.api.client.googleapis.auth.oauth2.GoogleIdTokenVerifier;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.json.gson.GsonFactory;

import jakarta.transaction.Transactional;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UsersRepo repo;
    private final RefreshTokenService refreshTokenService;
    private final VerificationTokenService tokenService;
    private final VerificationTokenRepository tokenrepo;
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

    public VerificationTokenService getTokenService() {
        return tokenService;
    }

    // ================= REGISTER =================

   public String register(RegisterRequest req) {
    
    Optional<Users> existingUser = repo.findByEmail(req.getEmail());

    if (existingUser.isPresent()) {
       
        if (existingUser.get().isVerified()) {
            throw new RuntimeException("Email already registered and verified!");
        }
      
        Users userToUpdate = existingUser.get();
        userToUpdate.setName(req.getName());
        userToUpdate.setPassword(encoder.encode(req.getPassword()));
        userToUpdate.setRole(Users.Role.valueOf(req.getRole().name()));
        
        repo.save(userToUpdate);
        generateAndSendOtp(userToUpdate.getEmail(), userToUpdate.getName(), "Account Verification");
        
        return "Registration updated! A new OTP has been sent to your email.";
    }

    // 4. If they don't exist at all, create new (your original logic)
    Users newUser = Users.builder()
            .name(req.getName())
            .email(req.getEmail())
            .password(encoder.encode(req.getPassword()))
            .role(Users.Role.valueOf(req.getRole().name()))
            .verified(false)
            .build();

    repo.save(newUser);
    generateAndSendOtp(newUser.getEmail(), newUser.getName(), "Account Verification");

    return "Registration successful! Check email for verification OTP.";
}

    // ================= VERIFY OTP =================

   public String verifyOtp(String email, String otpInput, String type) {
    // LOG 1: See exactly what the App sent
    System.out.println("DEBUG -> Email: [" + email + "] | OTP: [" + otpInput + "] | Type: [" + type + "]");

    if (!isOtpValid(email, otpInput)) {
        System.out.println("DEBUG -> OTP Check Failed: isOtpValid returned false");
        return "Invalid or expired OTP!";
    }

    if ("ACCOUNT".equalsIgnoreCase(type)) {
        System.out.println("DEBUG -> Processing ACCOUNT verification");
        Users user = repo.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found: " + email));

        user.setVerified(true);
        repo.save(user);

    } else if ("FORGOT".equalsIgnoreCase(type) || "RESET".equalsIgnoreCase(type)) {
        // Log both so you know which one hit
        System.out.println("DEBUG -> Processing FORGOT/RESET verification");
        otpVerifiedForReset.put(email, true);

    } else {
        // This catches the "Access Denied" or 500 error if type is wrong
        System.out.println("DEBUG -> ERROR: Unknown Type received: " + type);
        throw new RuntimeException("Invalid OTP type: " + type);
    }

    clearOtp(email);
    System.out.println("DEBUG -> Success!");
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

 

@Transactional
    public AuthResponse updateBasicInfo(UUID userId, BasicProfileDto dto) {
        Users user = repo.findById(userId).orElseThrow();
        
        user.setName(dto.getName());
        user.setPhoneNo(dto.getPhoneNo());
        user.setGender(dto.getGender());

        // FIX: Always re-check completion status after any update
        user.setComplete(isProfileFullyFilled(user));

        repo.save(user);
        return createAuthResponse(user);
    }
    
    @Transactional
    public AuthResponse updateLearningProfile(UUID userId, LearningPathDTO dto) {
        Users user = repo.findById(userId).orElseThrow();

        // Learning info
        user.setTargetCourse(dto.getTargetCourse());
        user.setCourseDuration(dto.getCourseDuration());
        user.setDailyStudyHours(dto.getDailyStudyHours());

        // Role-specific info
        if (user.getRole() == Users.Role.STUDENT) {
            user.setCollege(dto.getCollege());
            user.setUniversity(dto.getUniversity());
        }

        // Always re-check completion status
        user.setComplete(isProfileFullyFilled(user));

        repo.save(user);
        return createAuthResponse(user);
    }

    private boolean isProfileFullyFilled(Users user) {
        // 1. Mandatory for EVERYONE (including Basic Info)
        boolean hasIdentity = user.getName() != null && !user.getName().isBlank() &&
                             user.getPhoneNo() != null && !user.getPhoneNo().isBlank();

        // 2. Mandatory Learning Info
        boolean hasLearningInfo = user.getTargetCourse() != null && !user.getTargetCourse().isBlank() &&
                                 user.getCourseDuration() != null && !user.getCourseDuration().isBlank() &&
                                 user.getDailyStudyHours() != null && user.getDailyStudyHours() > 0;

        if (!hasIdentity || !hasLearningInfo) return false;

        // 3. Role-specific requirements
        if (user.getRole() == Users.Role.STUDENT) {
            return user.getCollege() != null && !user.getCollege().isBlank() &&
                   user.getUniversity() != null && !user.getUniversity().isBlank();
        }

        return true; // INDIVIDUAL only needs Identity + Learning Info
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
    RefreshToken refreshToken = refreshTokenService.createRefreshtoken(user.getEmail(), user.getId());

    return AuthResponse.builder()
            .accessToken(accessToken)
            .refreshToken(refreshToken.getToken())
            .id(user.getId().toString())
            .name(user.getName())
            .role(user.getRole().toString())
            .isComplete(user.isComplete()) // <--- Don't forget this!
            .build();
}

    private void generateAndSendOtp(String email, String name, String subject) {

        String otp = String.format("%04d", new Random().nextInt(10000));

        otpStore.put(email, otp);
        otpExpiry.put(email, System.currentTimeMillis() + OTP_EXPIRY_MS);

        emailService.sendOtpEmail(email, subject, name, otp);
    }

    @Transactional
    public void activateStudentAccount(String token, String newPassword) {
        // 1. Validate the token via the service
        var vToken = tokenService.validateToken(token)
                .orElseThrow(() -> new RuntimeException("Activation link is invalid or expired."));

        Users student = vToken.getUser();

        // 2. Set the real password and activate the account
        student.setPassword(encoder.encode(newPassword));
        student.setVerified(true);

        // 3. Optional: Mark profile as complete if the TPO provided enough info
        student.setComplete(isProfileFullyFilled(student));

        repo.save(student);

        // 4. Burn the token (one-time use)
        tokenService.deleteToken(vToken);
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
    @Transactional
    public void inviteBulkStudents(BulkRequest bulkRequest) {
        // 1. Get the TPO who is performing the action
        Users tpo = repo.findById(UUID.fromString(bulkRequest.getTpoId()))
                .orElseThrow(() -> new RuntimeException("TPO not found"));

        for (StudentBasicInfo studentInfo : bulkRequest.getStudents()) {
            try {
                if (repo.existsByEmail(studentInfo.getEmail())) {
                    continue;
                }

                String defaultPassword = studentInfo.getEmail();
                Users student = Users.builder()
                        .name(studentInfo.getName())
                        .email(studentInfo.getEmail())
                        .specialization(studentInfo.getSpecialization())
                        .college(bulkRequest.getCollege())
                        .university(bulkRequest.getUniversity())
                        .department(bulkRequest.getDepartment())
                        .courseDuration(bulkRequest.getCourseDuration())
                        .targetCourse(bulkRequest.getTargetCourse())
                        // Metadata
                        .invitedBy(tpo.getId())
                        .role(Users.Role.STUDENT)
                        .verified(true)        // <--- Verified immediately!
                        .isComplete(false)     // False so they must finish profile info
                        .createdAt(LocalDateTime.now())
                        .password(encoder.encode(defaultPassword))
                        .build();

                repo.save(student);

                // 3. Send Welcome Email with their credentials
                emailService.sendWelcomeEmail(student.getEmail(), student.getName(), defaultPassword);

            } catch (Exception e) {
                System.err.println("Error adding " + studentInfo.getEmail() + ": " + e.getMessage());
            }
        }
    }
    private void clearOtp(String email) {
        otpStore.remove(email);
        otpExpiry.remove(email);
    }
}