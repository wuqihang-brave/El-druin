"""
EL'druin Intelligence Platform – FastAPI Backend
=================================================

Main application entry point.

Run::

    python -m uvicorn app.main:app --reload --port 8001
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.news import router as news_router
from app.api.events import router as events_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Allow comma-separated origins via env var; default to localhost for development.
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(
    title="EL'druin Intelligence Platform API",
    description="Real-time news aggregation and event extraction API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(news_router)
app.include_router(events_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "EL'druin Intelligence Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "EL'druin API"}


logger.info("FastAPI application initialised")
