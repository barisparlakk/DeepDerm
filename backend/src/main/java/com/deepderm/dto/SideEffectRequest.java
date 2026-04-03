package com.deepderm.dto;

import jakarta.validation.constraints.NotBlank;

public class SideEffectRequest {

    @NotBlank
    private String drugName;

    @NotBlank
    private String description;

    public String getDrugName() { return drugName; }
    public void setDrugName(String drugName) { this.drugName = drugName; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
}
