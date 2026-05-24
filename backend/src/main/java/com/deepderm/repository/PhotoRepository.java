package com.deepderm.repository;

import com.deepderm.entity.Photo;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public interface PhotoRepository extends JpaRepository<Photo, UUID> {
    List<Photo> findByPatientIdOrderByUploadedAtDesc(UUID patientId);
    long countByPatientIdInAndQualityApprovedFalse(List<UUID> patientIds);
    long countByPatientIdInAndUploadedAtAfter(List<UUID> patientIds, Instant after);
    List<Photo> findTop6ByPatientIdInOrderByUploadedAtDesc(List<UUID> patientIds);
}
