package com.deepderm.dto;

import jakarta.validation.constraints.NotBlank;

public class EmergencyAlertRequest {

    @NotBlank
    private String message;

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
}
