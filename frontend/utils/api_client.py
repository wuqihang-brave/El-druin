import logging
import os
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 路径清洗逻辑：确保不重复叠加 /api/v1
_RAW_BACKEND = os.getenv("BACKEND_URL", "http://localhost:8001")
_CLEAN_BASE = _RAW_BACKEND.rstrip("/")
if _CLEAN_BASE.endswith("/api/v1"):
    _API_ROOT = _CLEAN_BASE
else:
    _API_ROOT = f"{_CLEAN_BASE}/api/v1"

class APIClient:
    """
    EL'druin API 客户端。
    已根据 app.py 源码补齐所有缺失方法，解决 AttributeError。
    """
    def __init__(self, base_url: str = _API_ROOT) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        logger.info(f"APIClient initialized with base_url: {self.base_url}")

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            r = self._session.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            r = self._session.post(url, json=json, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    # --- 1. 修复核心报错：系统状态页与主页渲染 ---
    
    def get_news_sources(self) -> Dict[str, Any]:
        """修复 AttributeError: 'APIClient' object has no attribute 'get_news_sources'"""
        return self._get("/news/sources")

    def get_hierarchical_graph(self, min_degree: int = 0, max_degree: int = 100) -> Dict[str, Any]:
        """修复 app.py 第 1383 行左右的报错"""
        return self._get("/knowledge/graph/hierarchy", params={"min_degree": min_degree, "max_degree": max_degree})

    def get_node_narrative(self, node_name: str) -> Dict[str, Any]:
        return self._get(f"/knowledge/graph/node-narrative/{node_name}")

    # --- 2. 知识图谱与推演 ---

    def ingest_knowledge_graph(self, limit: int = 100, hours: int = 24) -> Dict[str, Any]:
        return self._post("/knowledge/ingest", params={"limit": limit, "hours": hours})

    def grounded_deduce(self, news: Dict[str, Any]) -> Dict[str, Any]:
        """核心推演接口"""
        news_text = news.get("summary") or news.get("description") or news.get("content") or ""
        raw_entities = news.get("entities", [])
        seed_entities = [e.get("name", "") if isinstance(e, dict) else str(e) for e in raw_entities]
        
        return self._post("/analysis/grounded/deduce", json={
            "news_fragment": news_text,
            "seed_entities": [e for e in seed_entities if e],
            "claim": f"Impact analysis: {news.get('title', 'event')}"
        })

    # --- 3. 基础数据查询 ---

    def get_latest_news(self, limit: int = 20, hours: int = 24) -> Dict[str, Any]:
        return self._get("/news/latest", params={"limit": limit, "hours": hours})

    def get_kg_stats(self) -> Dict[str, Any]:
        return self._get("/knowledge/stats")

    def get_kg_entities(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/knowledge/entities", params={"limit": limit})

    def get_kg_relations(self, limit: int = 200) -> Dict[str, Any]:
        return self._get("/knowledge/relations")

    def health_check(self) -> Dict[str, Any]:
        return self._get("/health")

# 导出供外部使用的实例
api_client = APIClient()
