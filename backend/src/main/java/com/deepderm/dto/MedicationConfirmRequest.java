package com.deepderm.dto;

import jakarta.validation.constraints.NotNull;
import java.util.UUID;

public class MedicationConfirmRequest {

    @NotNull
    private UUID medicationId;

    public UUID getMedicationId() { return medicationId; }
    public void setMedicationId(UUID medicationId) { this.medicationId = medicationId; }
}
