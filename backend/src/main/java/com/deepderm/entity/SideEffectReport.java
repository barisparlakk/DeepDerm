package com.deepderm.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "side_effect_report")
public class SideEffectReport {

    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "patient_id", nullable = false)
    private Patient patient;

    @Column(name = "drug_name", nullable = false)
    private String drugName;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String description;

    @Column(name = "reported_at", nullable = false)
    private Instant reportedAt;

    @PrePersist void prePersist() { reportedAt = Instant.now(); }

    public SideEffectReport() {}

    public UUID getId() { return id; }
    public Patient getPatient() { return patient; }
    public void setPatient(Patient patient) { this.patient = patient; }
    public String getDrugName() { return drugName; }
    public void setDrugName(String drugName) { this.drugName = drugName; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public Instant getReportedAt() { return reportedAt; }
    public void setReportedAt(Instant reportedAt) { this.reportedAt = reportedAt; }
}
