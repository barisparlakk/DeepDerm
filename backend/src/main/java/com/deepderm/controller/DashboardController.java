package com.deepderm.controller;

import com.deepderm.entity.Doctor;
import com.deepderm.entity.Photo;
import com.deepderm.repository.EmergencyAlertRepository;
import com.deepderm.repository.PatientRepository;
import com.deepderm.repository.PhotoRepository;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

@RestController
@RequestMapping("/dashboard")
public class DashboardController {

    private final PatientRepository patientRepository;
    private final PhotoRepository photoRepository;
    private final EmergencyAlertRepository emergencyAlertRepository;

    @PersistenceContext
    private EntityManager em;

    public DashboardController(PatientRepository patientRepository,
                               PhotoRepository photoRepository,
                               EmergencyAlertRepository emergencyAlertRepository) {
        this.patientRepository = patientRepository;
        this.photoRepository = photoRepository;
        this.emergencyAlertRepository = emergencyAlertRepository;
    }

    @GetMapping
    public ResponseEntity<Map<String, Long>> getDashboard(@AuthenticationPrincipal Doctor doctor) {
        UUID doctorId = doctor.getId();
        long totalPatients = patientRepository.countByDoctorId(doctorId);
        List<UUID> patientIds = patientRepository.findByDoctorId(doctorId)
                .stream().map(p -> p.getId()).toList();

        long pendingReviews = patientIds.isEmpty() ? 0 :
                photoRepository.countByPatientIdInAndQualityApprovedFalse(patientIds);

        Instant sevenDaysAgo = Instant.now().minus(7, ChronoUnit.DAYS);
        long newPhotos = patientIds.isEmpty() ? 0 :
                photoRepository.countByPatientIdInAndUploadedAtAfter(patientIds, sevenDaysAgo);

        long emergencyAlerts = emergencyAlertRepository
                .findByPatientDoctorIdAndResolvedFalseOrderBySentAtDesc(doctorId).size();

        return ResponseEntity.ok(Map.of(
                "totalPatients", totalPatients,
                "pendingReviews", pendingReviews,
                "newPhotos", newPhotos,
                "emergencyAlerts", emergencyAlerts
        ));
    }

    /** GET /dashboard/severity-distribution — donut chart verisi */
    @GetMapping("/severity-distribution")
    public ResponseEntity<List<Map<String, Object>>> getSeverityDistribution(
            @AuthenticationPrincipal Doctor doctor) {

        List<UUID> patientIds = patientRepository.findByDoctorId(doctor.getId())
                .stream().map(p -> p.getId()).toList();

        if (patientIds.isEmpty()) return ResponseEntity.ok(List.of());

        @SuppressWarnings("unchecked")
        List<Object[]> rows = em.createNativeQuery(
                "SELECT a.severity->>'label' as label, a.severity->>'label_tr' as label_tr, COUNT(*) as cnt " +
                "FROM ai_analiz_sonuclari a " +
                "JOIN photo ph ON a.photo_id = ph.id " +
                "WHERE ph.patient_id IN (:ids) AND a.severity->>'label' IS NOT NULL " +
                "GROUP BY a.severity->>'label', a.severity->>'label_tr' " +
                "ORDER BY cnt DESC")
                .setParameter("ids", patientIds)
                .getResultList();

        List<Map<String, Object>> result = new ArrayList<>();
        for (Object[] row : rows) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("label",   row[0]);
            m.put("labelTr", row[1]);
            m.put("count",   ((Number) row[2]).longValue());
            result.add(m);
        }
        return ResponseEntity.ok(result);
    }

    /** GET /dashboard/recent-photos — son yüklenen 6 fotoğraf */
    @GetMapping("/recent-photos")
    public ResponseEntity<List<Map<String, Object>>> getRecentPhotos(
            @AuthenticationPrincipal Doctor doctor) {

        List<UUID> patientIds = patientRepository.findByDoctorId(doctor.getId())
                .stream().map(p -> p.getId()).toList();

        if (patientIds.isEmpty()) return ResponseEntity.ok(List.of());

        List<Photo> photos = photoRepository
                .findTop6ByPatientIdInOrderByUploadedAtDesc(patientIds);

        List<Map<String, Object>> result = new ArrayList<>();
        for (Photo ph : photos) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id",          ph.getId());
            m.put("fileUrl",     ph.getFileUrl());
            m.put("angle",       ph.getAngle());
            m.put("uploadedAt",  ph.getUploadedAt());
            m.put("patientId",   ph.getPatient().getId());
            m.put("patientName", ph.getPatient().getName() + " " + ph.getPatient().getSurname());
            result.add(m);
        }
        return ResponseEntity.ok(result);
    }
}
