package com.deepderm.repository;

import com.deepderm.entity.Patient;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface PatientRepository extends JpaRepository<Patient, UUID> {
    List<Patient> findByDoctorId(UUID doctorId);
    Optional<Patient> findByIdAndDoctorId(UUID id, UUID doctorId);
    Optional<Patient> findByEmail(String email);
}
