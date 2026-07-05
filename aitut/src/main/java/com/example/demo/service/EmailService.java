package com.example.demo.service;

import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class EmailService {

    private final JavaMailSender mailSender;

    public void sendOtpEmail(String to, String subject, String name, String otp) {
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");

            helper.setTo(to);
            helper.setSubject(subject);
            // Updated to reflect Ai-Tut branding
            helper.setFrom("no-reply@ai-tut.com");
            helper.setText(buildOtpHtml(name, otp), true);

            mailSender.send(message);
        } catch (Exception e) {
            throw new RuntimeException("Failed to send Ai-Tut verification email 💀", e);
        }
    }
    @Async
    public void sendWelcomeEmail(String to, String name, String password) {
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");

            helper.setTo(to);
            helper.setSubject("Welcome to Ai-Tut! Your account is ready 🚀");
            helper.setFrom("no-reply@ai-tut.com");

            // Pass the email and password to the HTML builder
            helper.setText(buildWelcomeHtml(name, to, password), true);

            mailSender.send(message);
        } catch (Exception e) {
            throw new RuntimeException("Failed to send Ai-Tut welcome email 💀", e);
        }
    }

    private String buildWelcomeHtml(String name, String email, String password) {
        return """
             <!DOCTYPE html>
             <html>
             <body style="margin:0;padding:0;background-color:#f4f6f8;font-family:Arial,sans-serif;">
               <table width="100%%" cellpadding="0" cellspacing="0">
                 <tr>
                   <td align="center" style="padding:40px 0;">
                     <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                       <tr>
                         <td style="background:#4f46e5;padding:20px;text-align:center;">
                           <span style="color:#ffffff;font-size:36px;font-weight:bold;">Ai-<span style="color:#fbbf24;">Tut</span></span>
                         </td>
                       </tr>
                       <tr>
                         <td style="padding:40px;color:#1f2937;">
                           <h2 style="margin:0;font-size:24px;">Welcome to the Team, %s!</h2>
                           <p style="margin-top:20px;font-size:16px;line-height:1.6;">
                             Your TPO has registered you on <b>Ai-Tut</b>. Your account is already verified and active. 
                             You can log in immediately using the credentials below:
                           </p>
                           
                           <div style="background:#f3f4f6; padding: 20px; border-radius: 8px; margin: 25px 0;">
                             <p style="margin: 5px 0;"><strong>Email:</strong> %s</p>
                             <p style="margin: 5px 0;"><strong>Password:</strong> <span style="color:#4f46e5; font-family: monospace; font-size: 18px;">%s</span></p>
                           </div>

                           <div style="margin:35px 0;text-align:center;">
                             <a href="https://ai-tut.com/login" style="background-color:#4f46e5;color:white;padding:15px 30px;text-decoration:none;font-size:18px;font-weight:bold;border-radius:8px;display:inline-block;">
                               Login Now
                             </a>
                           </div>
                           
                           <p style="font-size:14px;color:#ef4444;text-align:center;">
                             <b>Note:</b> For security, please complete your profile and update your password after logging in.
                           </p>
                         </td>
                       </tr>
                       <tr>
                         <td style="background:#f9fafb;color:#9ca3af;text-align:center;padding:20px;font-size:12px;">
                           © 2026 Ai-Tut Mentor Platform | Solapur, MH
                         </td>
                       </tr>
                     </table>
                   </td>
                 </tr>
               </table>
             </body>
             </html>
        """.formatted(name, email, password);
    }
    private String buildOtpHtml(String name, String otp) {
        return """
             <!DOCTYPE html>
             <html>
             <head>
               <meta charset="UTF-8">
               <title>Ai-Tut Verification</title>
             </head>
             <body style="margin:0;padding:0;background-color:#f4f6f8;font-family:Arial,sans-serif;">
               <table width="100%%" cellpadding="0" cellspacing="0">
                 <tr>
                   <td align="center" style="padding:40px 0;">
                     <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                       <tr>
                         <td style="background:#4f46e5;padding:20px;text-align:center;">
                           <span style="color:#ffffff;font-size:36px;font-weight:bold;">
                             Ai-<span style="color:#fbbf24;">Tut</span>
                           </span>
                         </td>
                       </tr>
                       <tr>
                         <td style="padding:40px;color:#1f2937;">
                           <h2 style="margin:0;font-size:24px;text-align:center;">Verify Your Account</h2>
                           <p style="margin-top:20px;font-size:16px;">Hello <b>%s</b>,</p>
                           <p style="font-size:15px;line-height:1.6;">
                             Welcome to Ai-Tut! We're excited to have you join our learning community. 
                             Please use the verification code below to complete your registration.
                           </p>
                           <div style="margin:30px 0;text-align:center;">
                             <span style="display:inline-block;font-size:32px;letter-spacing:8px;padding:15px 30px;background:#f3f4f6;color:#4f46e5;border:2px dashed #4f46e5;border-radius:8px;font-weight:bold;">
                               %s
                             </span>
                           </div>
                           <p style="font-size:14px;color:#6b7280;text-align:center;">
                             ⏱ This code is valid for <b>2 minutes</b>.
                           </p>
                         </td>
                       </tr>
                       <tr>
                         <td style="background:#f9fafb;color:#9ca3af;text-align:center;padding:20px;font-size:12px;">
                           © 2026 Ai-Tut Mentor Platform. All rights reserved.
                         </td>
                       </tr>
                     </table>
                   </td>
                 </tr>
               </table>
             </body>
             </html>
        """.formatted(name, otp);
    }


}