package com.deepderm.dto;

import jakarta.validation.constraints.NotBlank;

public class MedicationRequest {
    @NotBlank private String drugName;
    @NotBlank private String dosage;
    @NotBlank private String frequency;
    @NotBlank private String duration;
    private String instructions;

    public String getDrugName() { return drugName; }
    public void setDrugName(String drugName) { this.drugName = drugName; }
    public String getDosage() { return dosage; }
    public void setDosage(String dosage) { this.dosage = dosage; }
    public String getFrequency() { return frequency; }
    public void setFrequency(String frequency) { this.frequency = frequency; }
    public String getDuration() { return duration; }
    public void setDuration(String duration) { this.duration = duration; }
    public String getInstructions() { return instructions; }
    public void setInstructions(String instructions) { this.instructions = instructions; }
}
