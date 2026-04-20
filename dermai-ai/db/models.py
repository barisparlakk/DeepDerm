"""
models.py
=========
SQLAlchemy ORM model for the ai_analiz_sonuclari table.

This table is owned by the DermAI FastAPI service.
The Alembic migration in db/migrations/ creates it at startup.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class AiAnalizSonuclari(Base):
    """
    ai_analiz_sonuclari — stores one row per photo analysis.

    Columns
    -------
    id                  UUID PK (generated here, not by DB default)
    photo_id            UUID FK → photo.id
    patient_id          UUID FK → patient.id
    detections          JSONB   — list of detection objects
    total_lesion_count  INTEGER
    annotated_image_url TEXT    — relative URL served by FastAPI static files
    model_version       TEXT    — e.g. "yolov8n-v1-demo"
    analyzed_at         TIMESTAMPTZ
    """
    __tablename__ = "ai_analiz_sonuclari"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    detections: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    total_lesion_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    annotated_image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
