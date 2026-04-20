"""
database.py
===========
SQLAlchemy async engine and session factory.

Reads connection string from env var DEEPDERM_DB_URL (falls back to
a local dev default that matches the Spring Boot application.yml).
"""
from __future__ import annotations

import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Async PostgreSQL URL — use asyncpg driver
# Matches Spring Boot's datasource (replace jdbc:postgresql → postgresql+asyncpg)
_DEFAULT_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/deepderm"
DATABASE_URL = os.getenv("DEEPDERM_DB_URL", _DEFAULT_URL)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # set True locally to see SQL
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models in this service."""
    pass


# ── FastAPI dependency ─────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session
