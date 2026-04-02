package com.deepderm.repository;

import com.deepderm.entity.NoteRead;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface NoteReadRepository extends JpaRepository<NoteRead, UUID> {
    boolean existsByPatientIdAndNoteId(UUID patientId, UUID noteId);
    List<NoteRead> findByPatientId(UUID patientId);
    long countByPatientId(UUID patientId);
}
