"""
EL'druin Intelligence Platform – FastAPI Backend
=================================================

Start with::

    cd backend
    uvicorn app.main:app --reload --port 8001

API prefix: /api/v1
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.extract import router as extract_router
from app.api.routes.health import router as health_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.news import router as news_router

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
# Routes
# ---------------------------------------------------------------------------
_API_PREFIX = "/api/v1"

app.include_router(health_router, prefix=_API_PREFIX)
app.include_router(news_router, prefix=_API_PREFIX)
app.include_router(knowledge_router, prefix=_API_PREFIX)
app.include_router(extract_router, prefix=_API_PREFIX)
app.include_router(intelligence_router, prefix=_API_PREFIX)


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
