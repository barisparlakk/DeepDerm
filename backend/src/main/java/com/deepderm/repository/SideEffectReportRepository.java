package com.deepderm.repository;

import com.deepderm.entity.SideEffectReport;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface SideEffectReportRepository extends JpaRepository<SideEffectReport, UUID> {
    List<SideEffectReport> findByPatientIdOrderByReportedAtDesc(UUID patientId);
}
