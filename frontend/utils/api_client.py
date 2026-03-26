import logging
import os
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

# 自动处理路径，确保 /api/v1 逻辑正确
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
_base = BACKEND_URL.rstrip("/")
_DEFAULT_BASE_URL = f"{_base}/api/v1" if not _base.endswith("/api/v1") else _base

class APIClient:
    def __init__(self, base_url: str = _DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.post(url, json=json, params=params, timeout=45)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # --- 1. 修复主页与系统状态页报错 (CRITICAL) ---
    def get_hierarchical_graph(self, min_degree: int = 0, max_degree: int = 100):
        return self._get("/knowledge/graph/hierarchy", params={"min_degree": min_degree, "max_degree": max_degree})

    def get_news_sources(self):
        """修复 AttributeError: 'APIClient' object has no attribute 'get_news_sources'"""
        return self._get("/news/sources")

    def get_node_narrative(self, node_name: str):
        return self._get(f"/knowledge/graph/node-narrative/{node_name}")

    # --- 2. 知识图谱管理 ---
    def ingest_knowledge_graph(self, limit: int = 100, hours: int = 24):
        return self._post("/knowledge/ingest", params={"limit": limit, "hours": hours})

    def get_kg_stats(self):
        return self._get("/knowledge/stats")

    def get_kg_entities(self, limit: int = 100):
        return self._get("/knowledge/entities", params={"limit": limit})

    def get_kg_relations(self, limit: int = 200):
        return self._get("/knowledge/relations")

    # --- 3. 新闻与推演 ---
    def get_latest_news(self, limit: int = 20, hours: int = 24):
        return self._get("/news/latest", params={"limit": limit, "hours": hours})

    def ingest_news(self, include_newsapi: bool = False):
        return self._post("/news/ingest", params={"include_newsapi": include_newsapi})

    def grounded_deduce(self, news: Dict[str, Any]):
        news_text = news.get("summary") or news.get("description") or news.get("content") or ""
        raw_entities = news.get("entities", [])
        seed_entities = [e.get("name", "") if isinstance(e, dict) else str(e) for e in raw_entities]
        
        return self._post("/analysis/grounded/deduce", json={
            "news_fragment": news_text,
            "seed_entities": [e for e in seed_entities if e],
            "claim": f"Impact of {news.get('title', 'Event')}"
        })

    # --- 4. 其他 app.py 可能调用的辅助方法 ---
    def get_provenance_relationship(self, rel_id: str):
        return self._get(f"/provenance/relationship/{rel_id}")

    def get_entity_provenance(self, ent_id: str):
        return self._get(f"/provenance/entity/{ent_id}")

    def health_check(self):
        return self._get("/health")

api_client = APIClient()
