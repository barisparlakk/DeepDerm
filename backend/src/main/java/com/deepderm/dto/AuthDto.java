package com.deepderm.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class AuthDto {

    public static class LoginRequest {
        @NotBlank @Email
        private String email;
        @NotBlank @Size(min = 4)
        private String password;

        public String getEmail() { return email; }
        public void setEmail(String email) { this.email = email; }
        public String getPassword() { return password; }
        public void setPassword(String password) { this.password = password; }
    }

    public static class LoginResponse {
        private String token;
        private String doctorId;
        private String name;
        private String email;

        public LoginResponse(String token, String doctorId, String name, String email) {
            this.token = token;
            this.doctorId = doctorId;
            this.name = name;
            this.email = email;
        }

        public String getToken() { return token; }
        public String getDoctorId() { return doctorId; }
        public String getName() { return name; }
        public String getEmail() { return email; }
    }
}
