-- DeepDerm PostgreSQL Schema
-- Migration V1: Initial schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── doctor ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctor (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    email        VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── patient ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patient (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(100) NOT NULL,
    surname    VARCHAR(100) NOT NULL,
    age        INTEGER NOT NULL CHECK (age > 0 AND age < 150),
    gender     VARCHAR(10) NOT NULL,
    doctor_id  UUID NOT NULL REFERENCES doctor(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_patient_doctor ON patient(doctor_id);

-- ─── photo ───────────────────────────────────────────────────────────────────
CREATE TYPE photo_angle AS ENUM ('front', 'right', 'left');

CREATE TABLE IF NOT EXISTS photo (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id       UUID NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    angle            photo_angle NOT NULL,
    file_url         TEXT NOT NULL,
    uploaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    quality_approved BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_photo_patient ON photo(patient_id);

-- ─── medication ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medication (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id   UUID NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    drug_name    VARCHAR(255) NOT NULL,
    dosage       VARCHAR(100) NOT NULL,
    frequency    VARCHAR(100) NOT NULL,
    duration     VARCHAR(100) NOT NULL,
    instructions TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_medication_patient ON medication(patient_id);

-- ─── side_effect_report ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS side_effect_report (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  UUID NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    drug_name   VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_side_effect_patient ON side_effect_report(patient_id);

-- ─── emergency_alert ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS emergency_alert (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    message    TEXT NOT NULL,
    sent_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_alert_patient ON emergency_alert(patient_id);
CREATE INDEX idx_alert_unresolved ON emergency_alert(patient_id) WHERE resolved = FALSE;

-- ─── doctor_note ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctor_note (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    doctor_id  UUID NOT NULL REFERENCES doctor(id) ON DELETE CASCADE,
    note_text  TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_note_patient ON doctor_note(patient_id);

-- ─── ai_label ────────────────────────────────────────────────────────────────
CREATE TYPE ai_label_value AS ENUM ('improvement', 'stable', 'worsening');

CREATE TABLE IF NOT EXISTS ai_label (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id          UUID NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
    label             ai_label_value NOT NULL,
    parametric_values JSONB,
    labeled_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_label_photo ON ai_label(photo_id);

-- ─── Seed: demo doctor ───────────────────────────────────────────────────────
-- Password: DeepDerm2024! (bcrypt hash)
INSERT INTO doctor (name, email, password_hash)
VALUES (
    'Dr. Ayşe Kaya',
    'ayse.kaya@deripoliklinigi.com',
    '$2a$12$vE5y7RlD/Mok6ZkHgGUGMuFE.bJ2NzFQM6G9Gl6ZGNz1PVSOkjdpO'
)
ON CONFLICT (email) DO NOTHING;
