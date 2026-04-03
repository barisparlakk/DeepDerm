package com.deepderm.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "ai_label")
public class AiLabel {

    public enum Label { improvement, stable, worsening }

    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "photo_id", nullable = false)
    private Photo photo;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private Label label;

    @Column(name = "parametric_values", columnDefinition = "jsonb")
    private String parametricValues;

    @Column(name = "labeled_at", nullable = false)
    private Instant labeledAt;

    public AiLabel() {}

    public UUID getId() { return id; }
    public Photo getPhoto() { return photo; }
    public void setPhoto(Photo photo) { this.photo = photo; }
    public Label getLabel() { return label; }
    public void setLabel(Label label) { this.label = label; }
    public String getParametricValues() { return parametricValues; }
    public void setParametricValues(String parametricValues) { this.parametricValues = parametricValues; }
    public Instant getLabeledAt() { return labeledAt; }
    public void setLabeledAt(Instant labeledAt) { this.labeledAt = labeledAt; }
}
