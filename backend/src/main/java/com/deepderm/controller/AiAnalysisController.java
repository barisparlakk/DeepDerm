package com.deepderm.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.Map;
import java.util.UUID;

/**
 * AiAnalysisController
 * ====================
 * Proxies GET /api/ai/results/{photoId} to the DermAI FastAPI microservice
 * so the frontend only needs to talk to the Spring Boot backend.
 *
 * The doctor web panel fetches analysis results through this endpoint.
 */
@RestController
@RequestMapping("/ai")
public class AiAnalysisController {

    private static final Duration TIMEOUT = Duration.ofSeconds(10);

    private final WebClient webClient;

    public AiAnalysisController(
            @Value("${app.ai-module-url:http://localhost:8000}") String aiModuleUrl
    ) {
        this.webClient = WebClient.builder()
                .baseUrl(aiModuleUrl)
                .build();
    }

    /**
     * GET /api/ai/results/{photoId}
     * Proxies to the DermAI service and returns the stored analysis JSON.
     * Returns 404 when no analysis exists yet.
     */
    @GetMapping("/results/{photoId}")
    public ResponseEntity<Map<String, Object>> getResults(@PathVariable UUID photoId) {
        try {
            Map<String, Object> result = webClient.get()
                    .uri("/results/{photoId}", photoId)
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .timeout(TIMEOUT)
                    .block();
            return ResponseEntity.ok(result);
        } catch (WebClientResponseException.NotFound e) {
            return ResponseEntity.notFound().build();
        } catch (Exception e) {
            return ResponseEntity.status(503)
                    .body(Map.of("error", "AI service unavailable: " + e.getMessage()));
        }
    }

    /**
     * GET /api/ai/results/patient/{patientId}/timeline
     * Returns all stored AI analysis rows for a patient, newest first.
     */
    @GetMapping("/results/patient/{patientId}/timeline")
    public ResponseEntity<Map<String, Object>> getPatientTimeline(@PathVariable UUID patientId) {
        try {
            Map<String, Object> result = webClient.get()
                    .uri("/results/patient/{patientId}/timeline", patientId)
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .timeout(TIMEOUT)
                    .block();
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            return ResponseEntity.status(503)
                    .body(Map.of("error", "AI service unavailable: " + e.getMessage()));
        }
    }

    /**
     * GET /api/ai/compare?previousPhotoId=...&currentPhotoId=...
     * Proxies T1-T2 follow-up comparison to DermAI.
     */
    @GetMapping("/compare")
    public ResponseEntity<Map<String, Object>> compare(
            @RequestParam UUID previousPhotoId,
            @RequestParam UUID currentPhotoId
    ) {
        try {
            Map<String, Object> result = webClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .path("/compare")
                            .queryParam("previous_photo_id", previousPhotoId)
                            .queryParam("current_photo_id", currentPhotoId)
                            .build())
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .timeout(TIMEOUT)
                    .block();
            return ResponseEntity.ok(result);
        } catch (WebClientResponseException.NotFound e) {
            return ResponseEntity.notFound().build();
        } catch (WebClientResponseException.BadRequest e) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", e.getResponseBodyAsString()));
        } catch (Exception e) {
            return ResponseEntity.status(503)
                    .body(Map.of("error", "AI service unavailable: " + e.getMessage()));
        }
    }

    /**
     * GET /api/ai/health
     * Returns the DermAI service health status (useful for admin dashboards).
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        try {
            Map<String, Object> result = webClient.get()
                    .uri("/health")
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .timeout(Duration.ofSeconds(5))
                    .block();
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            return ResponseEntity.status(503)
                    .body(Map.of("status", "unavailable", "error", e.getMessage()));
        }
    }
}
