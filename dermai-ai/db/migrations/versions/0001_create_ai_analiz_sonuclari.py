"""
0001_create_ai_analiz_sonuclari.py
===================================
Initial migration:
  - Creates the ai_analiz_sonuclari table
  - Adds annotated_image_url column to the existing photo table

Run from dermai-ai/ directory:
    alembic upgrade head
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ai_analiz_sonuclari ────────────────────────────────────────────────────
    op.create_table(
        "ai_analiz_sonuclari",
        sa.Column("id",                  UUID(as_uuid=True), primary_key=True),
        sa.Column("photo_id",            UUID(as_uuid=True),
                  sa.ForeignKey("photo.id",   ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id",          UUID(as_uuid=True),
                  sa.ForeignKey("patient.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detections",          JSONB,              nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("total_lesion_count",  sa.Integer(),       nullable=False, server_default=sa.text("0")),
        sa.Column("annotated_image_url", sa.Text(),          nullable=True),
        sa.Column("model_version",       sa.String(100),     nullable=True),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_ai_analiz_photo_id",
        "ai_analiz_sonuclari",
        ["photo_id"],
    )
    op.create_index(
        "ix_ai_analiz_patient_id",
        "ai_analiz_sonuclari",
        ["patient_id"],
    )

    # ── photo table — add annotated_image_url column (IF NOT EXISTS) ──────────
    # We use execute() with raw SQL so the migration is idempotent.
    op.execute(
        "ALTER TABLE photo ADD COLUMN IF NOT EXISTS annotated_image_url TEXT"
    )


def downgrade() -> None:
    op.drop_index("ix_ai_analiz_patient_id", table_name="ai_analiz_sonuclari")
    op.drop_index("ix_ai_analiz_photo_id",   table_name="ai_analiz_sonuclari")
    op.drop_table("ai_analiz_sonuclari")
    op.execute(
        "ALTER TABLE photo DROP COLUMN IF EXISTS annotated_image_url"
    )
