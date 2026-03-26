"""
API Client – Optimized for EL'druin Intelligence Platform.
Fixed: Method name mismatch and path prefixing.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# --- 路径兼容逻辑 ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
_url_stripped = BACKEND_URL.rstrip("/")
# 确保 API 根路径始终包含 /api/v1
if not _url_stripped.endswith("/api/v1"):
    _DEFAULT_BASE_URL = f"{_url_stripped}/api/v1"
else:
    _DEFAULT_BASE_URL = _url_stripped

_TIMEOUT = 45  # 增加超时，给 LLM 推演留出时间

class APIClient:
    """Thin HTTP wrapper for the EL'druin FastAPI backend."""

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

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.post(url, json=json, params=params, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Error [POST %s]: %s", path, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # 1. 修复主页报错的核心方法 (Hierarchical Graph)
    # ------------------------------------------------------------------
    
    def get_hierarchical_graph(self, min_degree: int = 0, max_degree: int = 100) -> Dict[str, Any]:
        """获取本体层级图数据，修复 app.py 第 1383 行左右的报错"""
        return self._get("/knowledge/graph/hierarchy", params={"min_degree": min_degree, "max_degree": max_degree})

    def get_node_narrative(self, node_name: str) -> Dict[str, Any]:
        """获取特定节点的叙事背景"""
        return self._get(f"/knowledge/graph/node-narrative/{node_name}")

    # ------------------------------------------------------------------
    # 2. 知识图谱管理 (修复 Ingest 报错)
    # ------------------------------------------------------------------

    def ingest_knowledge_graph(self, limit: int = 100, hours: int = 24) -> Dict[str, Any]:
        """触发后端从新闻中提取并构建图谱节点"""
        return self._post("/knowledge/ingest", params={"limit": limit, "hours": hours})

    def get_kg_stats(self) -> Dict[str, Any]:
        return self._get("/knowledge/stats")

    def get_kg_entities(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/knowledge/entities", params={"limit": limit})

    def get_kg_relations(self, limit: int = 200) -> Dict[str, Any]:
        return self._get("/knowledge/relations", params={"limit": limit})

    # ------------------------------------------------------------------
    # 3. 本体论推演 (Palantir 核心)
    # ------------------------------------------------------------------

    def grounded_deduce(self, news: Dict[str, Any]) -> Dict[str, Any]:
        """发送推演请求，自动处理实体提取"""
        news_text = news.get("summary") or news.get("description") or news.get("content") or ""
        title = news.get("title", "未知事件")
        raw_entities = news.get("entities", [])

        seed_entities = []
        if isinstance(raw_entities, list):
            for e in raw_entities:
                if isinstance(e, dict): seed_entities.append(e.get("name", ""))
                else: seed_entities.append(str(e))
        
        return self._post(
            "/analysis/grounded/deduce",
            json={
                "news_fragment": news_text,
                "seed_entities": [e for e in seed_entities if e],
                "claim": f"分析事件的影响力: {title}",
            },
        )

    # ------------------------------------------------------------------
    # 4. 新闻源与系统功能
    # ------------------------------------------------------------------

    def get_latest_news(self, limit: int = 20, hours: int = 24) -> Dict[str, Any]:
        return self._get("/news/latest", params={"limit": limit, "hours": hours})

    def get_news_sources(self) -> Dict[str, Any]:
        """修复系统状态页调用缺失"""
        return self._get("/news/sources")

    def health_check(self) -> Dict[str, Any]:
        return self._get("/health")

# 导出单例
api_client = APIClient()
