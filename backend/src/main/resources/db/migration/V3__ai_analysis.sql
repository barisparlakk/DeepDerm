-- DeepDerm Migration V3: AI Analysis module support
-- Creates ai_analiz_sonuclari table and adds annotated_image_url to photo.
--
-- Note: The Alembic migration in dermai-ai/ handles the same tables.
-- This Flyway script ensures Spring Boot's DDL-validate mode passes.
-- Both scripts are idempotent (IF NOT EXISTS / IF NOT EXISTS).

-- ─── ai_analiz_sonuclari ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_analiz_sonuclari (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id            UUID        NOT NULL REFERENCES photo(id)   ON DELETE CASCADE,
    patient_id          UUID        NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    detections          JSONB       NOT NULL DEFAULT '[]'::jsonb,
    total_lesion_count  INTEGER     NOT NULL DEFAULT 0,
    annotated_image_url TEXT,
    model_version       VARCHAR(100),
    analyzed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ai_analiz_photo_id
    ON ai_analiz_sonuclari(photo_id);

CREATE INDEX IF NOT EXISTS ix_ai_analiz_patient_id
    ON ai_analiz_sonuclari(patient_id);

-- ─── photo — annotated_image_url column ───────────────────────────────────────
ALTER TABLE photo
    ADD COLUMN IF NOT EXISTS annotated_image_url TEXT;
