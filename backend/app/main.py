"""EL'druin Intelligence Platform - FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan: startup and shutdown."""
    logger.info("Starting EL'druin Intelligence Platform...")

    # PostgreSQL
    try:
        from app.db.postgres import init_db

        await init_db()
        logger.info("PostgreSQL initialized")
    except Exception as exc:
        logger.warning("PostgreSQL init failed: %s", exc)

    # Neo4j
    try:
        from app.db.neo4j_client import neo4j_client

        await neo4j_client.connect()
        logger.info("Neo4j connected")
    except Exception as exc:
        logger.warning("Neo4j connection failed: %s", exc)

    # Redis
    try:
        from app.db.redis_client import redis_client

        await redis_client.connect()
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning("Redis connection failed: %s", exc)

    logger.info("All services initialized — platform ready")
    yield

    logger.info("Shutting down EL'druin Intelligence Platform...")

    try:
        from app.db.neo4j_client import neo4j_client

        await neo4j_client.close()
    except Exception as exc:
        logger.warning("Neo4j close error: %s", exc)

    try:
        from app.db.redis_client import redis_client

        await redis_client.close()
    except Exception as exc:
        logger.warning("Redis close error: %s", exc)

    try:
        from app.db.postgres import engine

        await engine.dispose()
    except Exception as exc:
        logger.warning("Postgres dispose error: %s", exc)

    logger.info("Shutdown complete")


app = FastAPI(
    title="EL'druin Intelligence Platform",
    version="1.0.0",
    description="Enterprise-grade, ontology-driven intelligence platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from app.api.events import router as events_router
from app.api.predictions import router as predictions_router
from app.api.analysis import router as analysis_router
from app.api.watchlist import router as watchlist_router
from app.api.kg import router as kg_router
from app.api.websocket import router as ws_router

API_PREFIX = "/api/v1"

for router in (
    events_router,
    predictions_router,
    analysis_router,
    watchlist_router,
    kg_router,
):
    app.include_router(router, prefix=API_PREFIX)

app.include_router(ws_router)  # WebSocket routes have their own prefix


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Return platform health status."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(UTC).isoformat(),
    }
