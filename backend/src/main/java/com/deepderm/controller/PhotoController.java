package com.deepderm.controller;

import com.deepderm.dto.AiLabelRequest;
import com.deepderm.entity.AiLabel;
import com.deepderm.entity.Doctor;
import com.deepderm.entity.Photo;
import com.deepderm.repository.AiLabelRepository;
import com.deepderm.repository.PhotoRepository;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.UUID;

@RestController
@RequestMapping("/photos")
public class PhotoController {

    private final PhotoRepository photoRepository;
    private final AiLabelRepository aiLabelRepository;

    public PhotoController(PhotoRepository photoRepository, AiLabelRepository aiLabelRepository) {
        this.photoRepository = photoRepository;
        this.aiLabelRepository = aiLabelRepository;
    }

    @PostMapping("/{id}/label")
    public ResponseEntity<AiLabel> addLabel(@PathVariable UUID id,
                                             @Valid @RequestBody AiLabelRequest req,
                                             @AuthenticationPrincipal Doctor doctor) {
        Photo photo = photoRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Fotoğraf bulunamadı"));
        if (!photo.getPatient().getDoctor().getId().equals(doctor.getId())) {
            return ResponseEntity.status(403).build();
        }
        AiLabel label = new AiLabel();
        label.setPhoto(photo);
        label.setLabel(req.getLabel());
        label.setParametricValues(req.getParametricValues());
        label.setLabeledAt(Instant.now());
        return ResponseEntity.ok(aiLabelRepository.save(label));
    }
}
