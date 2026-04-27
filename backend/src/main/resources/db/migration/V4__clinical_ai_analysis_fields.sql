-- DeepDerm Migration V4: clinical AI analysis fields

ALTER TABLE ai_analiz_sonuclari
    ADD COLUMN IF NOT EXISTS counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS severity JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS quality JSONB,
    ADD COLUMN IF NOT EXISTS inflammatory_total INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS weighted_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS clinical_summary TEXT;

