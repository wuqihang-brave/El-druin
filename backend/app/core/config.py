"""
Application configuration loaded from environment variables.

All secrets and tuneable parameters are read from env vars (or a .env file
in the repo root via python-dotenv).  No hard-coded credentials.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
# 1. 精確定位項目根目錄 (El-druin)
# 假設 config.py 在 backend/app/core/config.py
# parents[0]=core, parents[1]=app, parents[2]=backend, parents[3]=El-druin
BASE_DIR = Path(__file__).resolve().parents[3]
# Load .env from repo root if present

load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings:
    """Central configuration object populated from environment variables."""
    # ── LLM ──────────────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
    # Preferred provider: "openai" | "groq" | "none"
    llm_provider: str = os.getenv("LLM_PROVIDER", "none")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    # Explicit kill-switch: set LLM_ENABLED=false to skip all LLM calls and
    # rely on rule-based extraction only (useful when the API key is invalid).
    _llm_enabled_env: bool = os.getenv("LLM_ENABLED", "true").lower() not in ("false", "0", "no")

    # ── Graph database ────────────────────────────────────────────────────────
    # "kuzu" (default, embedded) | "neo4j" | "networkx" (in-memory fallback)
    # Always resolve to an absolute path based on the project root so that
    # all entry points (server, scripts, tests) share the same physical file.
    graph_backend: str = os.getenv("GRAPH_BACKEND", "kuzu")
    _default_db_path: str = str(BASE_DIR / "data" / "el_druin.kuzu")
    kuzu_db_path: str = os.getenv("KUZU_DB_PATH", str(BASE_DIR / "data" / "el_druin.kuzu"))
    # Path for the embedded Kuzu knowledge-graph file (KuzuKnowledgeGraph)
    kuzu_kg_path: str = os.getenv("KUZU_KG_PATH", str(BASE_DIR / "data" / "el_druin.kuzu"))
    neo4j_uri: Optional[str] = os.getenv("NEO4J_URI")
    neo4j_user: Optional[str] = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: Optional[str] = os.getenv("NEO4J_PASSWORD")

    # ── News / feeds ──────────────────────────────────────────────────────────
    newsapi_key: Optional[str] = os.getenv("NEWSAPI_KEY")
    news_fetch_timeout: int = int(os.getenv("NEWS_FETCH_TIMEOUT", "15"))
    news_ingest_interval_minutes: int = int(os.getenv("NEWS_INGEST_INTERVAL_MINUTES", "30"))

    # ── FastAPI ───────────────────────────────────────────────────────────────
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8001"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ── RSS feed sources (comma-separated URLs, optional override) ────────────
    _rss_override: Optional[str] = os.getenv("RSS_FEED_URLS")

    @property
    def rss_feed_urls(self) -> List[str]:
        if self._rss_override:
            return [u.strip() for u in self._rss_override.split(",") if u.strip()]
        return []

    @property
    def llm_enabled(self) -> bool:
        """True when LLM is enabled via env var AND a provider + API key are set.

        If LLM_ENABLED=false is set explicitly, LLM is always disabled.
        If LLM_ENABLED=true (default) but no API key is configured, a warning
        is emitted and the setting is treated as False so rule-based extraction
        is used instead.
        """
        _log = logging.getLogger(__name__)

        if not self._llm_enabled_env:
            return False

        if self.llm_provider == "openai":
            if self.openai_api_key:
                return True
            _log.warning(
                "LLM_ENABLED=true but OPENAI_API_KEY is not set — "
                "falling back to rule-based extraction"
            )
            return False

        if self.llm_provider == "groq":
            if self.groq_api_key:
                return True
            _log.warning(
                "LLM_ENABLED=true but GROQ_API_KEY is not set — "
                "falling back to rule-based extraction"
            )
            return False

        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
