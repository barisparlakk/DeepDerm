package com.deepderm.repository;

import com.deepderm.entity.DoctorNote;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface DoctorNoteRepository extends JpaRepository<DoctorNote, UUID> {
    List<DoctorNote> findByPatientIdOrderByCreatedAtDesc(UUID patientId);
    long countByPatientId(UUID patientId);
}
