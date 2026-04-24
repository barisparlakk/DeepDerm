package com.deepderm.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

/**
 * DTO matching the JSON response returned by the DermAI FastAPI service
 * on POST /analyze.
 */
public class AiAnalysisResponse {

    @JsonProperty("photo_id")
    private String photoId;

    @JsonProperty("patient_id")
    private String patientId;

    private List<Detection> detections;

    @JsonProperty("total_lesion_count")
    private int totalLesionCount;

    @JsonProperty("annotated_image_url")
    private String annotatedImageUrl;

    @JsonProperty("model_version")
    private String modelVersion;

    @JsonProperty("analyzed_at")
    private String analyzedAt;

    public AiAnalysisResponse() {}

    // ── Nested Detection ──────────────────────────────────────────────────────

    public static class Detection {
        private String label;

        @JsonProperty("label_en")
        private String labelEn;

        private double confidence;

        private Map<String, Integer> bbox;

        public String getLabel()                    { return label; }
        public void   setLabel(String label)        { this.label = label; }
        public String getLabelEn()                  { return labelEn; }
        public void   setLabelEn(String labelEn)    { this.labelEn = labelEn; }
        public double getConfidence()               { return confidence; }
        public void   setConfidence(double c)       { this.confidence = c; }
        public Map<String, Integer> getBbox()       { return bbox; }
        public void   setBbox(Map<String, Integer> b) { this.bbox = b; }
    }

    // ── Getters / Setters ─────────────────────────────────────────────────────

    public String          getPhotoId()                         { return photoId; }
    public void            setPhotoId(String photoId)           { this.photoId = photoId; }
    public String          getPatientId()                       { return patientId; }
    public void            setPatientId(String patientId)       { this.patientId = patientId; }
    public List<Detection> getDetections()                      { return detections; }
    public void            setDetections(List<Detection> d)     { this.detections = d; }
    public int             getTotalLesionCount()                { return totalLesionCount; }
    public void            setTotalLesionCount(int c)           { this.totalLesionCount = c; }
    public String          getAnnotatedImageUrl()               { return annotatedImageUrl; }
    public void            setAnnotatedImageUrl(String url)     { this.annotatedImageUrl = url; }
    public String          getModelVersion()                    { return modelVersion; }
    public void            setModelVersion(String v)            { this.modelVersion = v; }
    public String          getAnalyzedAt()                      { return analyzedAt; }
    public void            setAnalyzedAt(String a)              { this.analyzedAt = a; }
}
