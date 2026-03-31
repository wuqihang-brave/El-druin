"""
Application configuration loaded from environment variables.

All secrets and tuneable parameters are read from env vars (or a .env file
in the repo root via python-dotenv).  No hard-coded credentials.
"""

from __future__ import annotations

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
    # ── Graph database ────────────────────────────────────────────────────────
    # 【核心修改】強行使用絕對路徑，並統一名稱為 el_druin.kuzu
    # 這樣無論你在哪裡啟動，路徑永遠是 /Users/qihang/.../El-druin/data/el_druin.kuzu
    graph_backend: str = os.getenv("GRAPH_BACKEND", "kuzu")
    
    _default_db_path = str(BASE_DIR / "data" / "el_druin.kuzu")
    kuzu_db_path: str = os.getenv("KUZU_DB_PATH", _default_db_path)
    
    # 兼容舊變量名 (如果你其他文件引用了這個名)
    kuzu_kg_path: str = os.getenv("KUZU_KG_PATH", _default_db_path)
    # ── LLM ──────────────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
    # Preferred provider: "openai" | "groq" | "none"
    llm_provider: str = os.getenv("LLM_PROVIDER", "none")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    # ── Graph database ────────────────────────────────────────────────────────
    # "kuzu" (default, embedded) | "neo4j" | "networkx" (in-memory fallback)
    graph_backend: str = os.getenv("GRAPH_BACKEND", "kuzu")
    kuzu_db_path: str = os.getenv("KUZU_DB_PATH", "./data/el_druin.kuzu")
    # Path for the embedded Kuzu knowledge-graph file (KuzuKnowledgeGraph)
    kuzu_kg_path: str = os.getenv("KUZU_KG_PATH", "./data/el_druin.kuzu")
    neo4j_uri: Optional[str] = os.getenv("NEO4J_URI")
    neo4j_user: Optional[str] = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: Optional[str] = os.getenv("NEO4J_PASSWORD")

    # ── News / feeds ──────────────────────────────────────────────────────────
    newsapi_key: Optional[str] = os.getenv("NEWSAPI_KEY")
    news_fetch_timeout: int = int(os.getenv("NEWS_FETCH_TIMEOUT", "15"))

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
        """True when an LLM API key is configured and a provider is set."""
        if self.llm_provider == "openai" and self.openai_api_key:
            return True
        if self.llm_provider == "groq" and self.groq_api_key:
            return True
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
