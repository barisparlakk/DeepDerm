package com.deepderm.repository;

import com.deepderm.entity.Medication;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface MedicationRepository extends JpaRepository<Medication, UUID> {
    List<Medication> findByPatientIdOrderByCreatedAtDesc(UUID patientId);
}
