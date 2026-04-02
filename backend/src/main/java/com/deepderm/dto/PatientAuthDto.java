package com.deepderm.dto;

import jakarta.validation.constraints.*;

public class PatientAuthDto {

    public static class RegisterRequest {
        @NotBlank
        private String name;

        @NotBlank
        private String surname;

        @NotNull @Min(1) @Max(149)
        private Integer age;

        @NotBlank
        private String gender;

        @NotBlank @Email
        private String email;

        @NotBlank @Size(min = 6)
        private String password;

        @AssertTrue(message = "KVKK onayı zorunludur")
        private boolean kvkkConsent;

        public String getName() { return name; }
        public void setName(String name) { this.name = name; }
        public String getSurname() { return surname; }
        public void setSurname(String surname) { this.surname = surname; }
        public Integer getAge() { return age; }
        public void setAge(Integer age) { this.age = age; }
        public String getGender() { return gender; }
        public void setGender(String gender) { this.gender = gender; }
        public String getEmail() { return email; }
        public void setEmail(String email) { this.email = email; }
        public String getPassword() { return password; }
        public void setPassword(String password) { this.password = password; }
        public boolean isKvkkConsent() { return kvkkConsent; }
        public void setKvkkConsent(boolean kvkkConsent) { this.kvkkConsent = kvkkConsent; }
    }

    public static class LoginRequest {
        @NotBlank @Email
        private String email;

        @NotBlank
        private String password;

        public String getEmail() { return email; }
        public void setEmail(String email) { this.email = email; }
        public String getPassword() { return password; }
        public void setPassword(String password) { this.password = password; }
    }

    public static class LoginResponse {
        private String token;
        private String patientId;
        private String name;
        private String surname;
        private String email;
        private Integer photoUploadPeriodDays;

        public LoginResponse(String token, String patientId, String name, String surname,
                             String email, Integer photoUploadPeriodDays) {
            this.token = token;
            this.patientId = patientId;
            this.name = name;
            this.surname = surname;
            this.email = email;
            this.photoUploadPeriodDays = photoUploadPeriodDays;
        }

        public String getToken() { return token; }
        public String getPatientId() { return patientId; }
        public String getName() { return name; }
        public String getSurname() { return surname; }
        public String getEmail() { return email; }
        public Integer getPhotoUploadPeriodDays() { return photoUploadPeriodDays; }
    }

    public static class ChangePasswordRequest {
        @NotBlank
        private String currentPassword;

        @NotBlank @Size(min = 6)
        private String newPassword;

        public String getCurrentPassword() { return currentPassword; }
        public void setCurrentPassword(String currentPassword) { this.currentPassword = currentPassword; }
        public String getNewPassword() { return newPassword; }
        public void setNewPassword(String newPassword) { this.newPassword = newPassword; }
    }
}
