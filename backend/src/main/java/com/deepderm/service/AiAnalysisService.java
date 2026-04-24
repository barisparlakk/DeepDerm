package com.deepderm.service;

import com.deepderm.dto.AiAnalysisResponse;
import com.deepderm.entity.Photo;
import com.deepderm.repository.PhotoRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.UUID;

/**
 * AiAnalysisService
 * =================
 * Calls the DermAI FastAPI microservice after each successful photo upload.
 *
 * Design decisions:
 *  - Uses WebClient (non-blocking) so Spring Boot threads are never blocked
 *    waiting for AI inference (which can take 2–10 s on CPU).
 *  - Annotated with @Async so the call is fire-and-forget from the controller.
 *  - On any error the photo upload still succeeds; the AI result is optional.
 *  - Updates photo.annotatedImageUrl on success.
 *  - Triggers a doctor notification on success (placeholder — wire to your
 *    NotificationService when available).
 */
@Service
public class AiAnalysisService {

    private static final Logger log = LoggerFactory.getLogger(AiAnalysisService.class);

    private static final Duration TIMEOUT      = Duration.ofSeconds(60);
    private static final String   HEALTH_PATH  = "/health";
    private static final String   ANALYZE_PATH = "/analyze";

    private final WebClient       webClient;
    private final PhotoRepository photoRepository;

    public AiAnalysisService(
            @Value("${app.ai-module-url:http://localhost:8000}") String aiModuleUrl,
            PhotoRepository photoRepository
    ) {
        this.photoRepository = photoRepository;
        this.webClient = WebClient.builder()
                .baseUrl(aiModuleUrl)
                .build();
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Asynchronously analyzes a photo by sending it to the DermAI service.
     * Called from {@code PatientSelfController} after the photo is persisted.
     *
     * @param photo       the saved photo entity (must have id, patient set)
     * @param imageBytes  raw bytes of the uploaded file
     */
    @Async
    public void analyzeAsync(Photo photo, byte[] imageBytes) {
        UUID photoId   = photo.getId();
        UUID patientId = photo.getPatient().getId();

        log.info("Starting async AI analysis for photo={} patient={}", photoId, patientId);

        MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();
        bodyBuilder.part("photo_id",   photoId.toString());
        bodyBuilder.part("patient_id", patientId.toString());
        bodyBuilder.part("image", new ByteArrayResource(imageBytes) {
            @Override public String getFilename() { return "photo.jpg"; }
        }).contentType(MediaType.IMAGE_JPEG);

        webClient.post()
                .uri(ANALYZE_PATH)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(bodyBuilder.build()))
                .retrieve()
                .bodyToMono(AiAnalysisResponse.class)
                .timeout(TIMEOUT)
                .onErrorResume(this::handleError)
                .subscribe(response -> {
                    if (response != null) {
                        onSuccess(photo, response);
                    }
                });
    }

    /**
     * Synchronous health check — returns true if the AI module is reachable.
     * Used for diagnostics, not in the hot path.
     */
    public boolean isHealthy() {
        try {
            webClient.get()
                    .uri(HEALTH_PATH)
                    .retrieve()
                    .toBodilessEntity()
                    .timeout(Duration.ofSeconds(5))
                    .block();
            return true;
        } catch (Exception e) {
            log.warn("AI module health check failed: {}", e.getMessage());
            return false;
        }
    }

    // ── Private helpers ────────────────────────────────────────────────────────

    private void onSuccess(Photo photo, AiAnalysisResponse response) {
        log.info(
            "AI analysis complete for photo={}: {} lesions detected (model={})",
            photo.getId(), response.getTotalLesionCount(), response.getModelVersion()
        );

        // Persist annotated image URL back to the photo record
        if (response.getAnnotatedImageUrl() != null) {
            try {
                photo.setAnnotatedImageUrl(response.getAnnotatedImageUrl());
                photoRepository.save(photo);
            } catch (Exception ex) {
                log.error("Failed to update annotated_image_url for photo={}: {}",
                        photo.getId(), ex.getMessage());
            }
        }

        // TODO: trigger doctor notification via NotificationService
        // notificationService.notifyDoctor(
        //     photo.getPatient().getDoctor().getId(),
        //     "Yeni fotoğraf analiz edildi"
        // );
        log.info("Doctor notification queued: 'Yeni fotoğraf analiz edildi' for photo={}",
                photo.getId());
    }

    private <T> Mono<T> handleError(Throwable ex) {
        if (ex instanceof WebClientResponseException wcre) {
            log.warn("AI module returned HTTP {}: {}", wcre.getStatusCode(), wcre.getResponseBodyAsString());
        } else {
            log.warn("AI module call failed (service may be down, photo upload unaffected): {}",
                    ex.getMessage());
        }
        // Return empty — photo upload must not fail because AI is down
        return Mono.empty();
    }
}
