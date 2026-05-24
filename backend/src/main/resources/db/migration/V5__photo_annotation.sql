CREATE TABLE photo_annotation (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id    UUID NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
    doctor_id   UUID NOT NULL REFERENCES doctor(id) ON DELETE CASCADE,
    data        JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_annotation_photo ON photo_annotation(photo_id);
