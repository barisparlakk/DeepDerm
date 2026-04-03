package com.deepderm.controller;

import com.deepderm.entity.Doctor;
import com.deepderm.entity.EmergencyAlert;
import com.deepderm.entity.SideEffectReport;
import com.deepderm.repository.EmergencyAlertRepository;
import com.deepderm.repository.SideEffectReportRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.*;

@RestController
@RequestMapping("/notifications")
public class NotificationController {

    private final EmergencyAlertRepository emergencyAlertRepository;
    private final SideEffectReportRepository sideEffectReportRepository;

    public NotificationController(EmergencyAlertRepository emergencyAlertRepository,
                                   SideEffectReportRepository sideEffectReportRepository) {
        this.emergencyAlertRepository = emergencyAlertRepository;
        this.sideEffectReportRepository = sideEffectReportRepository;
    }

    @GetMapping
    public ResponseEntity<List<Map<String, Object>>> getNotifications(@AuthenticationPrincipal Doctor doctor) {
        List<Map<String, Object>> notifications = new ArrayList<>();

        // Emergency alerts (priority)
        List<EmergencyAlert> alerts = emergencyAlertRepository
                .findByPatientDoctorIdAndResolvedFalseOrderBySentAtDesc(doctor.getId());
        for (EmergencyAlert a : alerts) {
            Map<String, Object> n = new HashMap<>();
            n.put("id", a.getId());
            n.put("type", "emergency");
            n.put("patientId", a.getPatient().getId());
            n.put("patientName", a.getPatient().getName() + " " + a.getPatient().getSurname());
            n.put("message", a.getMessage());
            n.put("sentAt", a.getSentAt());
            n.put("read", false);
            notifications.add(n);
        }

        // Side effect reports (last 30 days)
        Instant cutoff = Instant.now().minusSeconds(30L * 24 * 3600);
        List<SideEffectReport> reports = sideEffectReportRepository.findAll()
                .stream()
                .filter(r -> r.getPatient().getDoctor().getId().equals(doctor.getId()))
                .filter(r -> r.getReportedAt().isAfter(cutoff))
                .sorted(Comparator.comparing(SideEffectReport::getReportedAt).reversed())
                .toList();
        for (SideEffectReport r : reports) {
            Map<String, Object> n = new HashMap<>();
            n.put("id", r.getId());
            n.put("type", "side_effect");
            n.put("patientId", r.getPatient().getId());
            n.put("patientName", r.getPatient().getName() + " " + r.getPatient().getSurname());
            n.put("message", r.getDrugName() + " için yan etki: " + r.getDescription());
            n.put("sentAt", r.getReportedAt());
            n.put("read", false);
            notifications.add(n);
        }

        return ResponseEntity.ok(notifications);
    }

    @PatchMapping("/{id}/read")
    public ResponseEntity<Void> markRead(@PathVariable UUID id, @AuthenticationPrincipal Doctor doctor) {
        emergencyAlertRepository.findById(id).ifPresent(alert -> {
            if (alert.getPatient().getDoctor().getId().equals(doctor.getId())) {
                alert.setResolved(true);
                emergencyAlertRepository.save(alert);
            }
        });
        return ResponseEntity.noContent().build();
    }
}
