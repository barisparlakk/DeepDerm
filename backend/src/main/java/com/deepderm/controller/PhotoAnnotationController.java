package com.deepderm.controller;

import com.deepderm.entity.Doctor;
import com.deepderm.entity.Photo;
import com.deepderm.entity.PhotoAnnotation;
import com.deepderm.repository.PhotoAnnotationRepository;
import com.deepderm.repository.PhotoRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/photos/{photoId}/annotations")
public class PhotoAnnotationController {

    private final PhotoAnnotationRepository annotationRepository;
    private final PhotoRepository photoRepository;

    public PhotoAnnotationController(PhotoAnnotationRepository annotationRepository,
                                     PhotoRepository photoRepository) {
        this.annotationRepository = annotationRepository;
        this.photoRepository = photoRepository;
    }

    @GetMapping
    public ResponseEntity<Map<String, Object>> getAnnotation(@PathVariable UUID photoId,
                                                              @AuthenticationPrincipal Doctor doctor) {
        var annotation = annotationRepository.findByPhotoId(photoId);
        if (annotation.isEmpty()) {
            return ResponseEntity.ok(Map.of("photoId", photoId, "data", "[]"));
        }
        var a = annotation.get();
        return ResponseEntity.ok(Map.of(
                "id", a.getId(),
                "photoId", photoId,
                "data", a.getData(),
                "updatedAt", a.getUpdatedAt()
        ));
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> saveAnnotation(@PathVariable UUID photoId,
                                                               @RequestBody Map<String, String> body,
                                                               @AuthenticationPrincipal Doctor doctor) {
        Photo photo = photoRepository.findById(photoId)
                .orElseThrow(() -> new RuntimeException("Photo not found"));

        PhotoAnnotation annotation = annotationRepository.findByPhotoId(photoId)
                .orElse(new PhotoAnnotation());

        annotation.setPhoto(photo);
        annotation.setDoctor(doctor);
        annotation.setData(body.getOrDefault("data", "[]"));
        annotation.setUpdatedAt(Instant.now());

        var saved = annotationRepository.save(annotation);
        return ResponseEntity.ok(Map.of(
                "id", saved.getId(),
                "photoId", photoId,
                "data", saved.getData(),
                "updatedAt", saved.getUpdatedAt()
        ));
    }
}
