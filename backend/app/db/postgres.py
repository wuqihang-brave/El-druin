"""Async PostgreSQL client using SQLAlchemy 2 + asyncpg."""

import asyncio
import logging
from typing import Any, AsyncGenerator, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=settings.ENVIRONMENT == "development",
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Declarative base (shared by all models)
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session; rollback on error.

    Yields:
        An :class:`AsyncSession` bound to the shared engine.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Helper query functions
# ---------------------------------------------------------------------------


async def execute(sql: str, params: Optional[dict] = None) -> Any:
    """Execute a raw SQL statement and return the CursorResult.

    Args:
        sql: Raw SQL string.
        params: Optional bind parameters.

    Returns:
        SQLAlchemy CursorResult.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql), params or {})
        await session.commit()
        return result


async def fetch_one(sql: str, params: Optional[dict] = None) -> Optional[dict]:
    """Fetch a single row as a dict.

    Args:
        sql: Raw SQL string.
        params: Optional bind parameters.

    Returns:
        Row dict or *None* if no rows match.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql), params or {})
        row = result.fetchone()
        return dict(row._mapping) if row else None


async def fetch_all(
    sql: str, params: Optional[dict] = None
) -> list[dict]:
    """Fetch all matching rows as dicts.

    Args:
        sql: Raw SQL string.
        params: Optional bind parameters.

    Returns:
        List of row dicts.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql), params or {})
        return [dict(r._mapping) for r in result.fetchall()]


async def fetch_val(sql: str, params: Optional[dict] = None) -> Any:
    """Fetch a single scalar value.

    Args:
        sql: Raw SQL string.
        params: Optional bind parameters.

    Returns:
        Scalar value or *None*.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql), params or {})
        return result.scalar()


# ---------------------------------------------------------------------------
# Initialisation with retry
# ---------------------------------------------------------------------------


async def _setup_pgvector(session: AsyncSession) -> None:
    """Create pgvector extension if not already present."""
    try:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.commit()
        logger.info("pgvector extension ready")
    except Exception as exc:
        logger.warning("pgvector setup skipped: %s", exc)
        await session.rollback()


async def init_db(max_retries: int = 5) -> None:
    """Create all tables and extensions, with exponential backoff on failure.

    Args:
        max_retries: Maximum number of connection attempts.

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                # Import all models so their tables are registered on Base.
                import app.models.event  # noqa: F401
                import app.models.prediction  # noqa: F401
                import app.models.analysis  # noqa: F401
                import app.models.ontology  # noqa: F401
                import app.models.user  # noqa: F401

                await conn.run_sync(Base.metadata.create_all)

            async with AsyncSessionLocal() as session:
                await _setup_pgvector(session)

            logger.info("Database tables created / verified")
            return
        except Exception as exc:
            logger.warning(
                "DB init attempt %d/%d failed: %s — retrying in %.1fs",
                attempt,
                max_retries,
                exc,
                delay,
            )
            if attempt == max_retries:
                raise RuntimeError(
                    f"Could not initialise database after {max_retries} attempts"
                ) from exc
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
