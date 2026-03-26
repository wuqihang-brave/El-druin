"""
API Client – Full Version for EL'druin.
Handles News, Knowledge Graph, and Grounded Deduction.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# --- 环境变量与路径处理 ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
base_url_cleaned = BACKEND_URL.rstrip("/")
if not base_url_cleaned.endswith("/api/v1"):
    _DEFAULT_BASE_URL = f"{base_url_cleaned}/api/v1"
else:
    _DEFAULT_BASE_URL = base_url_cleaned

_TIMEOUT = 45  # 增加到45秒，因为知识图谱摄入和LLM推演非常耗时

class APIClient:
    def __init__(self, base_url: str = _DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.get(url, params=params, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Error [GET %s]: %s", path, exc)
            return {"error": str(exc)}

    def _post(self, path: str, params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.post(url, params=params, json=json, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Error [POST %s]: %s", path, exc)
            return {"error": str(exc)}

    # --- 知识图谱核心方法 (修复报错点) ---
    def ingest_knowledge_graph(self, limit: int = 100, hours: int = 24) -> Dict[str, Any]:
        """触发后端将新闻转化为图谱节点"""
        return self._post("/knowledge/ingest", params={"limit": limit, "hours": hours})

    def get_kg_stats(self) -> Dict[str, Any]:
        return self._get("/knowledge/stats")

    def get_kg_entities(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/knowledge/entities", params={"limit": limit})

    def get_kg_relations(self, limit: int = 200) -> Dict[str, Any]:
        return self._get("/knowledge/relations", params={"limit": limit})

    # --- 本地推演核心接口 ---
    def grounded_deduce(self, news: Dict[str, Any]) -> Dict[str, Any]:
        news_text = news.get("summary") or news.get("description") or news.get("content") or ""
        title = news.get("title", "this event")
        raw_entities = news.get("entities", [])
        
        seed_entities = []
        if isinstance(raw_entities, list):
            for e in raw_entities:
                if isinstance(e, dict): seed_entities.append(e.get("name", ""))
                else: seed_entities.append(str(e))
        seed_entities = [e for e in seed_entities if e]

        return self._post(
            "/analysis/grounded/deduce",
            json={
                "news_fragment": news_text,
                "seed_entities": seed_entities,
                "claim": f"Impact of {title}",
            },
        )

    # --- 新闻与健康检查 ---
    def get_latest_news(self, limit: int = 20, hours: int = 24) -> Dict[str, Any]:
        return self._get("/news/latest", params={"limit": limit, "hours": hours})

    def ingest_news(self, include_newsapi: bool = False) -> Dict[str, Any]:
        return self._post("/news/ingest", params={"include_newsapi": include_newsapi})

    def health_check(self) -> Dict[str, Any]:
        return self._get("/health")

api_client = APIClient()
