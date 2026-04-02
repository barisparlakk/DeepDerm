-- DeepDerm PostgreSQL Schema
-- Migration V2: Patient auth + mobile app extras

-- ─── Patient auth columns ────────────────────────────────────────────────────
ALTER TABLE patient
    ADD COLUMN IF NOT EXISTS email         VARCHAR(255) UNIQUE,
    ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
    ADD COLUMN IF NOT EXISTS photo_upload_period_days INTEGER NOT NULL DEFAULT 30,
    ADD COLUMN IF NOT EXISTS last_photo_uploaded_at   TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_patient_email ON patient(email);

-- ─── medication_confirm ───────────────────────────────────────────────────────
-- Records when a patient confirmed they took a medication on a given day
CREATE TABLE IF NOT EXISTS medication_confirm (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id    UUID NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    medication_id UUID NOT NULL REFERENCES medication(id) ON DELETE CASCADE,
    confirmed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_med_confirm_patient ON medication_confirm(patient_id);

-- ─── note_read ────────────────────────────────────────────────────────────────
-- Tracks which doctor notes have been read by the patient
CREATE TABLE IF NOT EXISTS note_read (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    note_id    UUID NOT NULL REFERENCES doctor_note(id) ON DELETE CASCADE,
    read_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, note_id)
);

CREATE INDEX IF NOT EXISTS idx_note_read_patient ON note_read(patient_id);
