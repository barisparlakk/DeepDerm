package com.deepderm.controller;

import com.deepderm.dto.AuthDto;
import com.deepderm.entity.Doctor;
import com.deepderm.repository.DoctorRepository;
import com.deepderm.security.JwtTokenProvider;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/auth")
public class AuthController {

    private final DoctorRepository doctorRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    public AuthController(DoctorRepository doctorRepository, PasswordEncoder passwordEncoder,
                          JwtTokenProvider jwtTokenProvider) {
        this.doctorRepository = doctorRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@Valid @RequestBody AuthDto.LoginRequest req) {
        Doctor doctor = doctorRepository.findByEmail(req.getEmail())
                .orElseThrow(() -> new RuntimeException("Geçersiz kimlik bilgileri"));
        if (!passwordEncoder.matches(req.getPassword(), doctor.getPasswordHash())) {
            return ResponseEntity.status(401).body("Geçersiz kimlik bilgileri");
        }
        String token = jwtTokenProvider.generateToken(doctor.getEmail());
        return ResponseEntity.ok(new AuthDto.LoginResponse(
                token, doctor.getId().toString(), doctor.getName(), doctor.getEmail()));
    }
}
