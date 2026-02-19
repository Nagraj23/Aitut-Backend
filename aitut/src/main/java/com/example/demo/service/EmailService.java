package com.example.demo.service;

import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
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