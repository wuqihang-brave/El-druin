import logging
import os
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# --- 极简路径逻辑：只保留到端口号 ---
_RAW_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
# 彻底去掉结尾的所有斜杠和 /api/v1，交给具体方法去拼
_BASE_URL = _RAW_URL.replace("/api/v1", "").rstrip("/")

class APIClient:
    def __init__(self, base_url: str = _BASE_URL) -> None:
        self.base_url = base_url
        self._session = requests.Session()

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        # 统一补齐 /api/v1，防止 app.py 传参不一致
        if not path.startswith("/api/v1"):
            path = f"/api/v1{path}"
        url = f"{self.base_url}{path}"
        try:
            r = self._session.request(method, url, timeout=45, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"API Error on {url}: {e}")
            return {"error": str(e)}

    # --- 基础方法 ---
    def _get(self, path: str, params=None): return self._request("GET", path, params=params)
    def _post(self, path: str, json=None, params=None): return self._request("POST", path, json=json, params=params)

    # --- 修复新闻页面 (404 解决) ---
    def get_latest_news(self, limit=20, hours=24):
        return self._get("/news/latest", params={"limit": limit, "hours": hours})

    def get_news_sources(self):
        return self._get("/news/sources")

    # --- 修复主页图谱 ---
    def get_hierarchical_graph(self, min_degree=0, max_degree=100):
        return self._get("/knowledge/graph/hierarchy", params={"min_degree": min_degree, "max_degree": max_degree})

    # --- 核心：本体论推演 (不再为空的关键) ---
    def grounded_deduce(self, news: Dict[str, Any]):
        # 1. 提取文本
        text = news.get("summary") or news.get("content") or ""
        # 2. 提取实体
        entities = news.get("entities", [])
        seed_entities = [e.get("name") if isinstance(e, dict) else str(e) for e in entities if e]
        
        # 3. 发送请求
        return self._post("/analysis/grounded/deduce", json={
            "news_fragment": text,
            "seed_entities": seed_entities,
            "claim": f"分析事件的深层本体影响: {news.get('title', '未知事件')}"
        })

    # --- 其他必要方法 ---
    def ingest_knowledge_graph(self, limit=100, hours=24):
        return self._post("/knowledge/ingest", params={"limit": limit, "hours": hours})

    def get_kg_stats(self): return self._get("/knowledge/stats")
    def health_check(self): return self._get("/health")

api_client = APIClient()
