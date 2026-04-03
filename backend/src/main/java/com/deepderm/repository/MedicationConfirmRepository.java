package com.deepderm.repository;

import com.deepderm.entity.MedicationConfirm;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public interface MedicationConfirmRepository extends JpaRepository<MedicationConfirm, UUID> {
    List<MedicationConfirm> findByPatientIdOrderByConfirmedAtDesc(UUID patientId);
    boolean existsByPatientIdAndMedicationIdAndConfirmedAtAfter(UUID patientId, UUID medicationId, Instant after);
}
