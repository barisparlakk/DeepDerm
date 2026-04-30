package com.deepderm.dto;

public class AngleCheckResponse {
    private boolean valid;
    private String detectedAngle;
    private String message;

    public AngleCheckResponse() {
    }

    public AngleCheckResponse(boolean valid, String detectedAngle, String message) {
        this.valid = valid;
        this.detectedAngle = detectedAngle;
        this.message = message;
    }

    public boolean isValid() {
        return valid;
    }

    public void setValid(boolean valid) {
        this.valid = valid;
    }

    public String getDetectedAngle() {
        return detectedAngle;
    }

    public void setDetectedAngle(String detectedAngle) {
        this.detectedAngle = detectedAngle;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}
