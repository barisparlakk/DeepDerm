package com.deepderm.security;

import com.deepderm.repository.DoctorRepository;
import com.deepderm.repository.PatientRepository;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(JwtAuthenticationFilter.class);

    private final JwtTokenProvider jwtTokenProvider;
    private final DoctorRepository doctorRepository;
    private final PatientRepository patientRepository;

    public JwtAuthenticationFilter(JwtTokenProvider jwtTokenProvider,
                                   DoctorRepository doctorRepository,
                                   PatientRepository patientRepository) {
        this.jwtTokenProvider = jwtTokenProvider;
        this.doctorRepository = doctorRepository;
        this.patientRepository = patientRepository;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String token = extractToken(request);
        if (StringUtils.hasText(token) && jwtTokenProvider.validateToken(token)) {
            String email = jwtTokenProvider.getEmailFromToken(token);
            String role  = jwtTokenProvider.getRoleFromToken(token);

            if ("PATIENT".equals(role)) {
                patientRepository.findByEmail(email).ifPresent(patient -> {
                    var auth = new UsernamePasswordAuthenticationToken(
                            patient, null, List.of(new SimpleGrantedAuthority("ROLE_PATIENT")));
                    SecurityContextHolder.getContext().setAuthentication(auth);
                });
            } else {
                // Default: DOCTOR (handles old tokens without role claim)
                doctorRepository.findByEmail(email).ifPresent(doctor -> {
                    var auth = new UsernamePasswordAuthenticationToken(
                            doctor, null, List.of(new SimpleGrantedAuthority("ROLE_DOCTOR")));
                    SecurityContextHolder.getContext().setAuthentication(auth);
                });
            }
        }
        filterChain.doFilter(request, response);
    }

    private String extractToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (StringUtils.hasText(header) && header.startsWith("Bearer ")) {
            return header.substring(7);
        }
        return null;
    }
}
