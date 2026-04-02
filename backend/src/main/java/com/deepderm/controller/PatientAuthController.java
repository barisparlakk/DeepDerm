package com.deepderm.controller;

import com.deepderm.dto.PatientAuthDto;
import com.deepderm.entity.Doctor;
import com.deepderm.entity.Patient;
import com.deepderm.repository.DoctorRepository;
import com.deepderm.repository.PatientRepository;
import com.deepderm.security.JwtTokenProvider;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/auth/patient")
public class PatientAuthController {

    private final PatientRepository patientRepository;
    private final DoctorRepository doctorRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    public PatientAuthController(PatientRepository patientRepository,
                                 DoctorRepository doctorRepository,
                                 PasswordEncoder passwordEncoder,
                                 JwtTokenProvider jwtTokenProvider) {
        this.patientRepository = patientRepository;
        this.doctorRepository = doctorRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    /**
     * Patient self-registration.
     * MVP: auto-assigns the first doctor in the database (single-clinic assumption).
     */
    @PostMapping("/register")
    public ResponseEntity<?> register(@Valid @RequestBody PatientAuthDto.RegisterRequest req) {
        if (patientRepository.findByEmail(req.getEmail()).isPresent()) {
            return ResponseEntity.badRequest().body("Bu e-posta adresi zaten kayıtlı.");
        }

        // Single-clinic assumption: link to first available doctor
        Doctor doctor = doctorRepository.findAll().stream()
                .findFirst()
                .orElseThrow(() -> new RuntimeException("Sistemde kayıtlı doktor bulunamadı."));

        Patient patient = new Patient();
        patient.setName(req.getName());
        patient.setSurname(req.getSurname());
        patient.setAge(req.getAge());
        patient.setGender(req.getGender());
        patient.setEmail(req.getEmail());
        patient.setPasswordHash(passwordEncoder.encode(req.getPassword()));
        patient.setDoctor(doctor);

        patientRepository.save(patient);

        String token = jwtTokenProvider.generateToken(patient.getEmail(), "PATIENT");
        return ResponseEntity.ok(new PatientAuthDto.LoginResponse(
                token,
                patient.getId().toString(),
                patient.getName(),
                patient.getSurname(),
                patient.getEmail(),
                patient.getPhotoUploadPeriodDays()
        ));
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@Valid @RequestBody PatientAuthDto.LoginRequest req) {
        Patient patient = patientRepository.findByEmail(req.getEmail())
                .orElseThrow(() -> new RuntimeException("Geçersiz kimlik bilgileri"));

        if (patient.getPasswordHash() == null ||
                !passwordEncoder.matches(req.getPassword(), patient.getPasswordHash())) {
            return ResponseEntity.status(401).body("Geçersiz kimlik bilgileri");
        }

        String token = jwtTokenProvider.generateToken(patient.getEmail(), "PATIENT");
        return ResponseEntity.ok(new PatientAuthDto.LoginResponse(
                token,
                patient.getId().toString(),
                patient.getName(),
                patient.getSurname(),
                patient.getEmail(),
                patient.getPhotoUploadPeriodDays()
        ));
    }
}
