"""
0002_add_clinical_analysis_fields.py
=====================================
Adds clinical interpretation fields to ai_analiz_sonuclari.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_analiz_sonuclari",
        sa.Column("counts", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "ai_analiz_sonuclari",
        sa.Column("severity", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "ai_analiz_sonuclari",
        sa.Column("quality", JSONB, nullable=True),
    )
    op.add_column(
        "ai_analiz_sonuclari",
        sa.Column("inflammatory_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "ai_analiz_sonuclari",
        sa.Column("weighted_score", sa.Float(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "ai_analiz_sonuclari",
        sa.Column("clinical_summary", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_analiz_sonuclari", "clinical_summary")
    op.drop_column("ai_analiz_sonuclari", "weighted_score")
    op.drop_column("ai_analiz_sonuclari", "inflammatory_total")
    op.drop_column("ai_analiz_sonuclari", "quality")
    op.drop_column("ai_analiz_sonuclari", "severity")
    op.drop_column("ai_analiz_sonuclari", "counts")

