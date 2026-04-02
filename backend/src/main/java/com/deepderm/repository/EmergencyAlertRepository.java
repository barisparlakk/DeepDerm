package com.deepderm.repository;

import com.deepderm.entity.EmergencyAlert;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface EmergencyAlertRepository extends JpaRepository<EmergencyAlert, UUID> {
    List<EmergencyAlert> findByPatientIdOrderBySentAtDesc(UUID patientId);
    List<EmergencyAlert> findByPatientDoctorIdAndResolvedFalseOrderBySentAtDesc(UUID doctorId);
    long countByPatientIdAndSentAtAfter(UUID patientId, java.time.Instant after);
}
