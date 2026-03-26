"""
API Client – HTTP client for communicating with the EL'druin FastAPI backend.
Enhanced with Ontological Grounding and Path-Safe logic.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# --- 核心修复：路径处理逻辑 ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")

# 不再删除 /api/v1，而是确保它一定存在
base_url_cleaned = BACKEND_URL.rstrip("/")
if not base_url_cleaned.endswith("/api/v1"):
    _DEFAULT_BASE_URL = f"{base_url_cleaned}/api/v1"
else:
    _DEFAULT_BASE_URL = base_url_cleaned

_TIMEOUT = 30  # 推演需要 LLM 思考，超时时间设长一点

class APIClient:
    """Thin HTTP wrapper around the EL'druin FastAPI backend."""

    def __init__(self, base_url: str = _DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.get(url, params=params, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Error [GET %s]: %s", path, exc)
            return {"error": str(exc)}

    def _post(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.post(url, params=params, json=json, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Error [POST %s]: %s", path, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Grounded Deduction (The "Palantir" Heart)
    # ------------------------------------------------------------------

    def grounded_deduce(self, news: Dict[str, Any]) -> Dict[str, Any]:
        """
        核心推演接口：将新闻与知识图谱对齐。
        """
        # 兼容不同的数据格式
        news_text = news.get("summary") or news.get("description") or news.get("content") or ""
        title = news.get("title", "this event")
        raw_entities = news.get("entities", [])

        # 处理实体列表：从 dict 列表或 string 列表提取
        seed_entities = []
        if isinstance(raw_entities, list):
            for e in raw_entities:
                if isinstance(e, dict):
                    seed_entities.append(e.get("name", ""))
                else:
                    seed_entities.append(str(e))
        
        # 清洗空字符串
        seed_entities = [e for e in seed_entities if e]

        # 发送到后端，确保字段名与后端 Pydantic 模型一致
        return self._post(
            "/analysis/grounded/deduce",
            json={
                "news_fragment": news_text,
                "seed_entities": seed_entities,
                "claim": f"What will be the impact of {title}?",
            },
        )

    # ------------------------------------------------------------------
    # News & Knowledge Graph Endpoints
    # ------------------------------------------------------------------

    def get_latest_news(self, limit: int = 20, hours: int = 24) -> Dict[str, Any]:
        return self._get("/news/latest", params={"limit": limit, "hours": hours})

    def ingest_news(self, include_newsapi: bool = False) -> Dict[str, Any]:
        return self._post("/news/ingest", params={"include_newsapi": include_newsapi})

    def get_kg_stats(self) -> Dict[str, Any]:
        return self._get("/knowledge/stats")

    def get_kg_entities(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/knowledge/entities", params={"limit": limit})

    def get_kg_relations(self, limit: int = 200) -> Dict[str, Any]:
        return self._get("/knowledge/relations", params={"limit": limit})

    def health_check(self) -> Dict[str, Any]:
        return self._get("/health")

# 创建单例供 Streamlit 直接使用
api_client = APIClient()
