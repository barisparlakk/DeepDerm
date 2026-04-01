package com.deepderm.controller;

import com.deepderm.dto.MedicationRequest;
import com.deepderm.dto.NoteRequest;
import com.deepderm.entity.*;
import com.deepderm.repository.*;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/patients")
public class PatientController {

    private final PatientRepository patientRepository;
    private final PhotoRepository photoRepository;
    private final MedicationRepository medicationRepository;
    private final SideEffectReportRepository sideEffectReportRepository;
    private final EmergencyAlertRepository emergencyAlertRepository;
    private final DoctorNoteRepository doctorNoteRepository;

    public PatientController(PatientRepository patientRepository,
                             PhotoRepository photoRepository,
                             MedicationRepository medicationRepository,
                             SideEffectReportRepository sideEffectReportRepository,
                             EmergencyAlertRepository emergencyAlertRepository,
                             DoctorNoteRepository doctorNoteRepository) {
        this.patientRepository = patientRepository;
        this.photoRepository = photoRepository;
        this.medicationRepository = medicationRepository;
        this.sideEffectReportRepository = sideEffectReportRepository;
        this.emergencyAlertRepository = emergencyAlertRepository;
        this.doctorNoteRepository = doctorNoteRepository;
    }

    @GetMapping
    public List<Patient> getPatients(@AuthenticationPrincipal Doctor doctor) {
        return patientRepository.findByDoctorId(doctor.getId());
    }

    @GetMapping("/{id}")
    public ResponseEntity<Patient> getPatient(@PathVariable UUID id, @AuthenticationPrincipal Doctor doctor) {
        return patientRepository.findByIdAndDoctorId(id, doctor.getId())
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/photos")
    public ResponseEntity<List<Photo>> getPhotos(@PathVariable UUID id, @AuthenticationPrincipal Doctor doctor) {
        verifyAccess(id, doctor);
        return ResponseEntity.ok(photoRepository.findByPatientIdOrderByUploadedAtDesc(id));
    }

    @GetMapping("/{id}/medications")
    public ResponseEntity<List<Medication>> getMedications(@PathVariable UUID id, @AuthenticationPrincipal Doctor doctor) {
        verifyAccess(id, doctor);
        return ResponseEntity.ok(medicationRepository.findByPatientIdOrderByCreatedAtDesc(id));
    }

    @PostMapping("/{id}/medications")
    public ResponseEntity<Medication> addMedication(@PathVariable UUID id,
                                                    @Valid @RequestBody MedicationRequest req,
                                                    @AuthenticationPrincipal Doctor doctor) {
        Patient patient = verifyAccess(id, doctor);
        Medication med = new Medication();
        med.setPatient(patient);
        med.setDrugName(req.getDrugName());
        med.setDosage(req.getDosage());
        med.setFrequency(req.getFrequency());
        med.setDuration(req.getDuration());
        med.setInstructions(req.getInstructions());
        return ResponseEntity.ok(medicationRepository.save(med));
    }

    @GetMapping("/{id}/side-effects")
    public ResponseEntity<List<SideEffectReport>> getSideEffects(@PathVariable UUID id, @AuthenticationPrincipal Doctor doctor) {
        verifyAccess(id, doctor);
        return ResponseEntity.ok(sideEffectReportRepository.findByPatientIdOrderByReportedAtDesc(id));
    }

    @GetMapping("/{id}/emergency-alerts")
    public ResponseEntity<List<EmergencyAlert>> getEmergencyAlerts(@PathVariable UUID id, @AuthenticationPrincipal Doctor doctor) {
        verifyAccess(id, doctor);
        return ResponseEntity.ok(emergencyAlertRepository.findByPatientIdOrderBySentAtDesc(id));
    }

    @GetMapping("/{id}/notes")
    public ResponseEntity<List<DoctorNote>> getNotes(@PathVariable UUID id, @AuthenticationPrincipal Doctor doctor) {
        verifyAccess(id, doctor);
        return ResponseEntity.ok(doctorNoteRepository.findByPatientIdOrderByCreatedAtDesc(id));
    }

    @PostMapping("/{id}/notes")
    public ResponseEntity<DoctorNote> addNote(@PathVariable UUID id,
                                              @Valid @RequestBody NoteRequest req,
                                              @AuthenticationPrincipal Doctor doctor) {
        Patient patient = verifyAccess(id, doctor);
        DoctorNote note = new DoctorNote();
        note.setPatient(patient);
        note.setDoctor(doctor);
        note.setNoteText(req.getNoteText());
        return ResponseEntity.ok(doctorNoteRepository.save(note));
    }

    private Patient verifyAccess(UUID patientId, Doctor doctor) {
        return patientRepository.findByIdAndDoctorId(patientId, doctor.getId())
                .orElseThrow(() -> new RuntimeException("Hasta bulunamadı veya erişim reddedildi"));
    }
}
