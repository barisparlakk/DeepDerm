package com.deepderm.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "photo")
public class Photo {

    public enum Angle { front, right, left }

    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "patient_id", nullable = false)
    private Patient patient;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private Angle angle;

    @Column(name = "file_url", nullable = false)
    private String fileUrl;

    @Column(name = "uploaded_at", nullable = false)
    private Instant uploadedAt;

    @Column(name = "quality_approved")
    private Boolean qualityApproved = false;

    public Photo() {}

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public Patient getPatient() { return patient; }
    public void setPatient(Patient patient) { this.patient = patient; }
    public Angle getAngle() { return angle; }
    public void setAngle(Angle angle) { this.angle = angle; }
    public String getFileUrl() { return fileUrl; }
    public void setFileUrl(String fileUrl) { this.fileUrl = fileUrl; }
    public Instant getUploadedAt() { return uploadedAt; }
    public void setUploadedAt(Instant uploadedAt) { this.uploadedAt = uploadedAt; }
    public Boolean getQualityApproved() { return qualityApproved; }
    public void setQualityApproved(Boolean qualityApproved) { this.qualityApproved = qualityApproved; }
}
