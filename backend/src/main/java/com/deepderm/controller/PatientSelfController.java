package com.deepderm.controller;

import com.deepderm.dto.EmergencyAlertRequest;
import com.deepderm.dto.MedicationConfirmRequest;
import com.deepderm.dto.PatientAuthDto;
import com.deepderm.dto.SideEffectRequest;
import com.deepderm.entity.*;
import com.deepderm.repository.*;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * All patient-facing self-service endpoints.
 * Requires ROLE_PATIENT principal (injected by JwtAuthenticationFilter).
 */
@RestController
@RequestMapping("/patients/me")
public class PatientSelfController {

    private final PatientRepository patientRepository;
    private final MedicationRepository medicationRepository;
    private final SideEffectReportRepository sideEffectReportRepository;
    private final EmergencyAlertRepository emergencyAlertRepository;
    private final DoctorNoteRepository doctorNoteRepository;
    private final PhotoRepository photoRepository;
    private final MedicationConfirmRepository medicationConfirmRepository;
    private final NoteReadRepository noteReadRepository;
    private final PasswordEncoder passwordEncoder;

    @Value("${app.upload-dir:uploads}")
    private String uploadDir;

    public PatientSelfController(PatientRepository patientRepository,
                                 MedicationRepository medicationRepository,
                                 SideEffectReportRepository sideEffectReportRepository,
                                 EmergencyAlertRepository emergencyAlertRepository,
                                 DoctorNoteRepository doctorNoteRepository,
                                 PhotoRepository photoRepository,
                                 MedicationConfirmRepository medicationConfirmRepository,
                                 NoteReadRepository noteReadRepository,
                                 PasswordEncoder passwordEncoder) {
        this.patientRepository = patientRepository;
        this.medicationRepository = medicationRepository;
        this.sideEffectReportRepository = sideEffectReportRepository;
        this.emergencyAlertRepository = emergencyAlertRepository;
        this.doctorNoteRepository = doctorNoteRepository;
        this.photoRepository = photoRepository;
        this.medicationConfirmRepository = medicationConfirmRepository;
        this.noteReadRepository = noteReadRepository;
        this.passwordEncoder = passwordEncoder;
    }

    // ─── Profile ─────────────────────────────────────────────────────────────

    @GetMapping
    public ResponseEntity<Patient> getProfile(@AuthenticationPrincipal Patient patient) {
        return ResponseEntity.ok(patient);
    }

    @PutMapping("/password")
    public ResponseEntity<?> changePassword(@AuthenticationPrincipal Patient patient,
                                            @Valid @RequestBody PatientAuthDto.ChangePasswordRequest req) {
        if (!passwordEncoder.matches(req.getCurrentPassword(), patient.getPasswordHash())) {
            return ResponseEntity.status(400).body("Mevcut şifre hatalı.");
        }
        patient.setPasswordHash(passwordEncoder.encode(req.getNewPassword()));
        patientRepository.save(patient);
        return ResponseEntity.ok(Map.of("message", "Şifre başarıyla güncellendi."));
    }

    @DeleteMapping
    public ResponseEntity<?> deleteAccount(@AuthenticationPrincipal Patient patient) {
        patientRepository.delete(patient);
        return ResponseEntity.ok(Map.of("message", "Hesabınız kalıcı olarak silindi."));
    }

    // ─── Medications ─────────────────────────────────────────────────────────

    @GetMapping("/medications")
    public ResponseEntity<List<Medication>> getMedications(@AuthenticationPrincipal Patient patient) {
        return ResponseEntity.ok(medicationRepository.findByPatientIdOrderByCreatedAtDesc(patient.getId()));
    }

    // ─── Medication Confirm ───────────────────────────────────────────────────

    @PostMapping("/medication-confirm")
    public ResponseEntity<?> confirmMedication(@AuthenticationPrincipal Patient patient,
                                               @Valid @RequestBody MedicationConfirmRequest req) {
        Medication med = medicationRepository.findById(req.getMedicationId())
                .orElseThrow(() -> new RuntimeException("İlaç bulunamadı"));

        if (!med.getPatient().getId().equals(patient.getId())) {
            return ResponseEntity.status(403).body("Erişim reddedildi");
        }

        // Check if already confirmed today
        Instant startOfDay = Instant.now().truncatedTo(ChronoUnit.DAYS);
        boolean alreadyConfirmed = medicationConfirmRepository
                .existsByPatientIdAndMedicationIdAndConfirmedAtAfter(patient.getId(), med.getId(), startOfDay);
        if (alreadyConfirmed) {
            return ResponseEntity.badRequest().body("Bu ilacı bugün zaten onayladınız.");
        }

        MedicationConfirm confirm = new MedicationConfirm();
        confirm.setPatient(patient);
        confirm.setMedication(med);
        medicationConfirmRepository.save(confirm);
        return ResponseEntity.ok(Map.of("message", "İlaç alındı olarak kaydedildi."));
    }

    // ─── Doctor Notes ─────────────────────────────────────────────────────────

    @GetMapping("/doctor-notes")
    public ResponseEntity<List<DoctorNote>> getDoctorNotes(@AuthenticationPrincipal Patient patient) {
        return ResponseEntity.ok(doctorNoteRepository.findByPatientIdOrderByCreatedAtDesc(patient.getId()));
    }

    @GetMapping("/doctor-notes/unread-count")
    public ResponseEntity<Map<String, Long>> getUnreadNoteCount(@AuthenticationPrincipal Patient patient) {
        long total = doctorNoteRepository.countByPatientId(patient.getId());
        long read  = noteReadRepository.countByPatientId(patient.getId());
        long unread = Math.max(0, total - read);
        return ResponseEntity.ok(Map.of("unreadCount", unread));
    }

    @PostMapping("/doctor-notes/{noteId}/read")
    public ResponseEntity<?> markNoteRead(@AuthenticationPrincipal Patient patient,
                                          @PathVariable UUID noteId) {
        DoctorNote note = doctorNoteRepository.findById(noteId)
                .orElseThrow(() -> new RuntimeException("Not bulunamadı"));
        if (!note.getPatient().getId().equals(patient.getId())) {
            return ResponseEntity.status(403).body("Erişim reddedildi");
        }
        if (!noteReadRepository.existsByPatientIdAndNoteId(patient.getId(), noteId)) {
            NoteRead nr = new NoteRead();
            nr.setPatient(patient);
            nr.setNote(note);
            noteReadRepository.save(nr);
        }
        return ResponseEntity.ok(Map.of("message", "Not okundu olarak işaretlendi."));
    }

    // ─── Photos ──────────────────────────────────────────────────────────────

    @GetMapping("/photos")
    public ResponseEntity<List<Photo>> getPhotos(@AuthenticationPrincipal Patient patient) {
        return ResponseEntity.ok(photoRepository.findByPatientIdOrderByUploadedAtDesc(patient.getId()));
    }

    @PostMapping("/photos")
    public ResponseEntity<?> uploadPhoto(@AuthenticationPrincipal Patient patient,
                                         @RequestParam("file") MultipartFile file,
                                         @RequestParam("angle") String angle) throws IOException {
        // Check upload period (only enforced once all photos in a session are uploaded)
        // We allow upload if lastPhotoUploadedAt is null OR period has passed
        if (patient.getLastPhotoUploadedAt() != null) {
            long daysSinceLast = ChronoUnit.DAYS.between(patient.getLastPhotoUploadedAt(), Instant.now());
            int period = patient.getPhotoUploadPeriodDays() != null ? patient.getPhotoUploadPeriodDays() : 30;
            if (daysSinceLast < period) {
                long daysLeft = period - daysSinceLast;
                return ResponseEntity.badRequest()
                        .body("Fotoğraf yükleme periyodunuz dolmadı. " + daysLeft + " gün sonra tekrar yükleyebilirsiniz.");
            }
        }

        // Validate angle
        Photo.Angle photoAngle;
        try {
            photoAngle = Photo.Angle.valueOf(angle);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body("Geçersiz açı. front, right veya left olmalıdır.");
        }

        // Save file locally
        Path uploadPath = Paths.get(uploadDir, "photos", patient.getId().toString());
        Files.createDirectories(uploadPath);
        String filename = UUID.randomUUID() + "_" + angle + "_" +
                System.currentTimeMillis() + getExtension(file.getOriginalFilename());
        Path dest = uploadPath.resolve(filename);
        file.transferTo(dest);

        String fileUrl = "/uploads/photos/" + patient.getId() + "/" + filename;

        Photo photo = new Photo();
        photo.setPatient(patient);
        photo.setAngle(photoAngle);
        photo.setFileUrl(fileUrl);
        photo.setQualityApproved(false);
        photoRepository.save(photo);

        // Update lastPhotoUploadedAt
        patient.setLastPhotoUploadedAt(Instant.now());
        patientRepository.save(patient);

        return ResponseEntity.ok(photo);
    }

    // ─── Side Effects ─────────────────────────────────────────────────────────

    @GetMapping("/side-effects")
    public ResponseEntity<List<SideEffectReport>> getSideEffects(@AuthenticationPrincipal Patient patient) {
        return ResponseEntity.ok(sideEffectReportRepository.findByPatientIdOrderByReportedAtDesc(patient.getId()));
    }

    @PostMapping("/side-effects")
    public ResponseEntity<SideEffectReport> reportSideEffect(@AuthenticationPrincipal Patient patient,
                                                             @Valid @RequestBody SideEffectRequest req) {
        SideEffectReport report = new SideEffectReport();
        report.setPatient(patient);
        report.setDrugName(req.getDrugName());
        report.setDescription(req.getDescription());
        return ResponseEntity.ok(sideEffectReportRepository.save(report));
    }

    // ─── Emergency Alert ──────────────────────────────────────────────────────

    @GetMapping("/emergency-alert/status")
    public ResponseEntity<Map<String, Object>> getEmergencyStatus(@AuthenticationPrincipal Patient patient) {
        Instant startOfMonth = Instant.now().truncatedTo(ChronoUnit.DAYS)
                .minus(Instant.now().atZone(java.time.ZoneOffset.UTC).getDayOfMonth() - 1, ChronoUnit.DAYS);
        long usedThisMonth = emergencyAlertRepository
                .countByPatientIdAndSentAtAfter(patient.getId(), startOfMonth);
        boolean canSend = usedThisMonth < 1;
        return ResponseEntity.ok(Map.of(
                "canSend", canSend,
                "usedThisMonth", usedThisMonth,
                "monthlyLimit", 1
        ));
    }

    @PostMapping("/emergency-alert")
    public ResponseEntity<?> sendEmergencyAlert(@AuthenticationPrincipal Patient patient,
                                                @Valid @RequestBody EmergencyAlertRequest req) {
        // Check monthly quota
        Instant startOfMonth = Instant.now().truncatedTo(ChronoUnit.DAYS)
                .minus(Instant.now().atZone(java.time.ZoneOffset.UTC).getDayOfMonth() - 1, ChronoUnit.DAYS);
        long usedThisMonth = emergencyAlertRepository
                .countByPatientIdAndSentAtAfter(patient.getId(), startOfMonth);
        if (usedThisMonth >= 1) {
            return ResponseEntity.status(429)
                    .body("Bu ay acil bildirim hakkınızı kullandınız. Bir sonraki ayda tekrar kullanabilirsiniz.");
        }

        EmergencyAlert alert = new EmergencyAlert();
        alert.setPatient(patient);
        alert.setMessage(req.getMessage());
        return ResponseEntity.ok(emergencyAlertRepository.save(alert));
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private String getExtension(String filename) {
        if (filename == null || !filename.contains(".")) return ".jpg";
        return filename.substring(filename.lastIndexOf('.'));
    }
}
