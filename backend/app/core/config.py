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
from typing import ClassVar, List, Optional

from dotenv import load_dotenv
# 1. 精確定位項目根目錄 (El-druin)
# 假設 config.py 在 backend/app/core/config.py
# parents[0]=core, parents[1]=app, parents[2]=backend, parents[3]=El-druin
_computed = Path(__file__).resolve().parents[3]
# Fallback: if the computed root doesn't look like a valid project root
# (no data/ directory and no .env file), use the current working directory
# instead.  This handles Docker images, pip-installed packages, and other
# non-standard layouts where the source tree nesting differs.
if not (_computed / "data").is_dir() and not (_computed / ".env").is_file():
    BASE_DIR = Path.cwd()
else:
    BASE_DIR = _computed
# Load .env from repo root if present

load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings:
    """Central configuration object populated from environment variables.

    All environment-variable reads are performed inside ``__init__`` so that
    each ``Settings()`` instantiation reflects the current process environment.
    This matters in tests (which may patch ``os.environ``) and in any scenario
    where env vars are set *after* the module is first imported.
    """

    _DEFAULT_GROQ_MODEL: ClassVar[str] = "llama-3.1-8b-instant"
    _DEFAULT_OPENAI_MODEL: ClassVar[str] = "gpt-4o-mini"

    def __init__(self) -> None:
        # ── LLM ──────────────────────────────────────────────────────────────
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
        # Preferred provider: "openai" | "groq" | "none"
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "none")
        self.llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

        # Compute provider-aware default for llm_model.
        # Priority: explicit LLM_MODEL env var → provider default → gpt-4o-mini
        _llm_model_env = os.getenv("LLM_MODEL")
        if _llm_model_env:
            self.llm_model: str = _llm_model_env
        elif self.llm_provider == "groq":
            self.llm_model = self._DEFAULT_GROQ_MODEL
        elif self.llm_provider == "openai":
            self.llm_model = self._DEFAULT_OPENAI_MODEL
        else:
            self.llm_model = self._DEFAULT_OPENAI_MODEL

        # Explicit kill-switch: set LLM_ENABLED=false to skip all LLM calls
        # and rely on rule-based extraction only (useful when the API key is
        # invalid or missing).
        self._llm_enabled_env: bool = (
            os.getenv("LLM_ENABLED", "true").lower() not in ("false", "0", "no")
        )

        # ── Graph database ────────────────────────────────────────────────────
        # "kuzu" (default, embedded) | "neo4j" | "networkx" (in-memory fallback)
        # Always resolve to an absolute path based on the project root so that
        # all entry points (server, scripts, tests) share the same physical file.
        self.graph_backend: str = os.getenv("GRAPH_BACKEND", "kuzu")
        default_db_path = str(BASE_DIR / "data" / "el_druin.kuzu")
        self.kuzu_db_path: str = os.getenv("KUZU_DB_PATH", default_db_path)
        # Path for the embedded Kuzu knowledge-graph file (KuzuKnowledgeGraph)
        self.kuzu_kg_path: str = os.getenv("KUZU_KG_PATH", default_db_path)
        self.neo4j_uri: Optional[str] = os.getenv("NEO4J_URI")
        self.neo4j_user: Optional[str] = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password: Optional[str] = os.getenv("NEO4J_PASSWORD")

        # ── News / feeds ──────────────────────────────────────────────────────
        self.newsapi_key: Optional[str] = os.getenv("NEWSAPI_KEY")
        self.news_fetch_timeout: int = int(os.getenv("NEWS_FETCH_TIMEOUT", "15"))
        self.news_ingest_interval_minutes: int = int(
            os.getenv("NEWS_INGEST_INTERVAL_MINUTES", "30")
        )

        # ── FastAPI ───────────────────────────────────────────────────────────
        self.api_host: str = os.getenv("API_HOST", "0.0.0.0")
        self.api_port: int = int(os.getenv("API_PORT", "8001"))
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"

        # ── RSS feed sources (comma-separated URLs, optional override) ─────────
        self._rss_override: Optional[str] = os.getenv("RSS_FEED_URLS")

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
