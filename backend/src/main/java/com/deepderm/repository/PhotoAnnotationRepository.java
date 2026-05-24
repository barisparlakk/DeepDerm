package com.deepderm.repository;

import com.deepderm.entity.PhotoAnnotation;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface PhotoAnnotationRepository extends JpaRepository<PhotoAnnotation, UUID> {
    Optional<PhotoAnnotation> findByPhotoId(UUID photoId);
}
