"""
EL'druin Intelligence Platform – FastAPI Backend
=================================================

Start with::

    cd backend
    uvicorn app.main:app --reload --port 8001

API prefix: /api/v1
"""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analysis import router as analysis_router
from app.api.routes.assessments import router as assessments_router
from app.api.routes.entities import router as entities_router
from app.api.routes.extract import router as extract_router
from app.api.routes.health import router as health_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.news import router as news_router
from app.api.routes.provenance import router as provenance_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="EL'druin Intelligence Platform API",
    description=(
        "Real-time news aggregation, event extraction, and knowledge graph "
        "for the EL'druin open-source intelligence platform."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS (allow Streamlit frontend on any origin in development)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup event – initialise KuzuDB before any request is served
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    """Ensure KuzuDB directories and schemas exist before handling requests."""
    try:
        from app.core.db import initialize_database

        initialize_database()
        logger.info("✅ Database initialised successfully")
    except Exception as exc:
        logger.error("❌ Database initialisation failed: %s", exc)
        # Do not re-raise: let the app start so the /health endpoint remains
        # reachable and operators can diagnose the problem without a full
        # service outage.

    try:
        from app.core.assessment_store import assessment_store  # noqa: F401 – triggers init
        logger.info("✅ Assessment store initialised")
    except Exception as exc:
        logger.error("❌ Assessment store init failed: %s", exc)

    # Start background ingest scheduler
    try:
        from app.core.config import get_settings
        from app.services.ingest_scheduler import run_ingest_cycle
        interval = get_settings().news_ingest_interval_minutes
        asyncio.create_task(run_ingest_cycle(interval))
        logger.info("Ingest scheduler started (interval=%d min)", interval)
    except Exception as exc:
        logger.error("Ingest scheduler failed to start: %s", exc)

    # Run ontology algebra validation (warn-only in all environments).
    # Set DEBUG=true to enable strict mode (raises on error).
    try:
        from ontology.relation_schema import run_ontology_validation

        strict_mode = os.getenv("DEBUG", "false").lower() == "true"
        run_ontology_validation(strict=strict_mode)
    except Exception as exc:
        logger.warning("Ontology validation skipped: %s", exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
_API_PREFIX = "/api/v1"

app.include_router(health_router, prefix=_API_PREFIX)
app.include_router(news_router, prefix=_API_PREFIX)
app.include_router(knowledge_router, prefix=_API_PREFIX)
app.include_router(extract_router, prefix=_API_PREFIX)
app.include_router(intelligence_router, prefix=_API_PREFIX)
app.include_router(provenance_router, prefix=_API_PREFIX)
app.include_router(analysis_router, prefix=_API_PREFIX)
app.include_router(entities_router, prefix=_API_PREFIX)
app.include_router(assessments_router, prefix=_API_PREFIX, tags=["assessments"])


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"message": "EL'druin API – see /docs for the OpenAPI spec"}


# ---------------------------------------------------------------------------
# Dev entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    from app.core.config import get_settings

    cfg = get_settings()
    uvicorn.run(
        "app.main:app",
        host=cfg.api_host,
        port=cfg.api_port,
        reload=cfg.debug,
    )
