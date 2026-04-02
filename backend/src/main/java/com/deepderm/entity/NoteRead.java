package com.deepderm.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "note_read",
       uniqueConstraints = @UniqueConstraint(columnNames = {"patient_id", "note_id"}))
public class NoteRead {

    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "patient_id", nullable = false)
    private Patient patient;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "note_id", nullable = false)
    private DoctorNote note;

    @Column(name = "read_at", updatable = false)
    private Instant readAt;

    @PrePersist void prePersist() { readAt = Instant.now(); }

    public NoteRead() {}

    public UUID getId() { return id; }
    public Patient getPatient() { return patient; }
    public void setPatient(Patient patient) { this.patient = patient; }
    public DoctorNote getNote() { return note; }
    public void setNote(DoctorNote note) { this.note = note; }
    public Instant getReadAt() { return readAt; }
}
