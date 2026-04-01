#!/usr/bin/env python3
"""
checkg.py – 知識圖譜健康檢查與業務數據初始化腳本

用法（從項目根目錄運行）：
    PYTHONPATH=backend python checkg.py

功能：
1. 初始化 GraphStore，打印物理 DB 文件路徑
2. 批量寫入核心業務實體與關係（A/B 測試節點 + 主業務實體）
3. 讀回所有實體與邊，驗證寫入成功
4. 按樣本實體查詢 1-hop 鄰居，確認圖譜可查
"""

from __future__ import annotations

import sys
import os

# ── 確保 backend/ 在 Python 搜索路徑中 ──────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_HERE, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# ── 載入配置（會打印物理路徑） ────────────────────────────────────────────────
from app.core.config import get_settings  # noqa: E402

settings = get_settings()
_DB_PATH = settings.kuzu_db_path

print("=" * 60)
print("checkg.py – 知識圖譜健康檢查")
print("=" * 60)
print(f"📂 KuzuDB 物理路徑: {_DB_PATH}")

# ── 初始化 GraphStore ─────────────────────────────────────────────────────────
print("\n--- 初始化 GraphStore ---")
from app.knowledge.graph_store import GraphStore  # noqa: E402

store = GraphStore()

# ═══════════════════════════════════════════════════════════════════════════════
# A 測試：基礎功能驗證（A→B 節點）
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- A 測試：寫入並讀取基礎測試節點 ---")
store.add_entity("A", "TestNode")
store.add_entity("B", "TestNode")
store.add_relation("A", "TestNode", "B", "TestNode", "TEST_REL", 0.8)

a_neighbours = store.get_neighbours("A", depth=1)
a_b_count = len([n for n in a_neighbours if n.get("name") == "B"])
print(f"A 的鄰居中找到 B: {a_b_count} 次  (期望 ≥ 1)")

# ═══════════════════════════════════════════════════════════════════════════════
# 批量寫入主業務實體與關係
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- 批量寫入主業務實體與關係 ---")

entities = [
    ("United States", "Country"),
    ("China", "Country"),
    ("European Union", "Organization"),
    ("World Trade Organization", "Organization"),
    ("United Nations", "Organization"),
    ("Russia", "Country"),
    ("US-China relationship", "Concept"),
    ("Global economy", "Concept"),
    ("Tariffs", "Concept"),
    ("Intellectual property theft", "Event"),
    ("Forced technology transfers", "Event"),
    ("Syria", "Country"),
    ("Syrian government", "Organization"),
    ("Syrian opposition", "Organization"),
    ("Aleppo", "Location"),
    ("chemical weapons", "Concept"),
    ("economic sanctions", "Concept"),
    ("oil and gas", "Concept"),
    ("military aid", "Concept"),
    ("ceasefire", "Event"),
    ("conflict", "Event"),
    ("Security Council", "Organization"),
    ("NATO", "Organization"),
    ("Israel", "Country"),
    ("Iran", "Country"),
]

relations_data = [
    ("United States", "Country", "China", "Country", "RELATED_TO", 1.0),
    ("United States", "Country", "European Union", "Organization", "RELATED_TO", 0.9),
    ("United States", "Country", "Tariffs", "Concept", "PARTICIPATES_IN", 0.8),
    ("United States", "Country", "World Trade Organization", "Organization", "MEMBER_OF", 0.9),
    ("United States", "Country", "NATO", "Organization", "MEMBER_OF", 1.0),
    ("United States", "Country", "economic sanctions", "Concept", "PARTICIPATES_IN", 0.8),
    ("China", "Country", "World Trade Organization", "Organization", "MEMBER_OF", 0.9),
    ("China", "Country", "Intellectual property theft", "Event", "PARTICIPATES_IN", 0.8),
    ("China", "Country", "US-China relationship", "Concept", "RELATED_TO", 1.0),
    ("China", "Country", "Global economy", "Concept", "RELATED_TO", 0.8),
    ("European Union", "Organization", "World Trade Organization", "Organization", "MEMBER_OF", 0.9),
    ("European Union", "Organization", "NATO", "Organization", "RELATED_TO", 0.8),
    ("United Nations", "Organization", "Security Council", "Organization", "RELATED_TO", 1.0),
    ("United Nations", "Organization", "Syria", "Country", "RELATED_TO", 0.9),
    ("United Nations", "Organization", "ceasefire", "Event", "PARTICIPATES_IN", 0.9),
    ("Russia", "Country", "United Nations", "Organization", "MEMBER_OF", 1.0),
    ("Russia", "Country", "Syria", "Country", "RELATED_TO", 0.9),
    ("Russia", "Country", "Security Council", "Organization", "MEMBER_OF", 1.0),
    ("Global economy", "Concept", "US-China relationship", "Concept", "RELATED_TO", 1.0),
    ("Tariffs", "Concept", "Forced technology transfers", "Event", "RELATED_TO", 0.8),
    ("Tariffs", "Concept", "Global economy", "Concept", "RELATED_TO", 0.8),
    ("Syria", "Country", "Syrian government", "Organization", "RELATED_TO", 1.0),
    ("Syria", "Country", "Aleppo", "Location", "RELATED_TO", 1.0),
    ("Syria", "Country", "conflict", "Event", "PARTICIPATES_IN", 0.9),
    ("Syrian government", "Organization", "chemical weapons", "Concept", "PARTICIPATES_IN", 0.7),
    ("Syrian opposition", "Organization", "Syria", "Country", "RELATED_TO", 0.9),
    ("Syrian opposition", "Organization", "ceasefire", "Event", "PARTICIPATES_IN", 0.8),
    ("economic sanctions", "Concept", "Iran", "Country", "RELATED_TO", 0.9),
    ("economic sanctions", "Concept", "Russia", "Country", "RELATED_TO", 0.8),
    ("military aid", "Concept", "Syrian government", "Organization", "RELATED_TO", 0.8),
    ("military aid", "Concept", "Syrian opposition", "Organization", "RELATED_TO", 0.7),
    ("Israel", "Country", "Iran", "Country", "RELATED_TO", 0.8),
    ("Iran", "Country", "oil and gas", "Concept", "PARTICIPATES_IN", 0.9),
    ("ceasefire", "Event", "conflict", "Event", "RELATED_TO", 0.9),
]

for name, etype in entities:
    store.add_entity(name, etype)

for f, ft, t, tt, r, w in relations_data:
    store.add_relation(f, ft, t, tt, r, w)

# ═══════════════════════════════════════════════════════════════════════════════
# 驗證：讀回所有實體與邊
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- 驗證：讀取當前 KG 狀態 ---")
all_entities = store.get_entities(200)
all_relations = store.get_relations(500)
print(f"✅ 當前 KG 實體數量: {len(all_entities)}")
print(f"✅ 當前 KG 邊數量:   {len(all_relations)}")

# ═══════════════════════════════════════════════════════════════════════════════
# 樣本查詢：按幾個核心實體驗證 1-hop 鄰居
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- 樣本查詢：核心實體 1-hop 鄰居 ---")
sample_entities = ["United States", "China", "United Nations", "Syria"]
for entity in sample_entities:
    neighbours = store.get_neighbours(entity, depth=1)
    print(f"  {entity}: {len(neighbours)} 鄰居  "
          f"→ {[n.get('name', '') for n in neighbours[:3]]}")

# ═══════════════════════════════════════════════════════════════════════════════
# 可選：用 KuzuContextExtractor 直接驗證 1-hop + 2-hop（複用 GraphStore 連接）
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- KuzuContextExtractor 驗證（1-hop + 2-hop） ---")
try:
    from ontology.kuzu_context_extractor import KuzuContextExtractor

    # 複用 GraphStore 內部的 Kuzu 連接，避免同時打開兩個連接
    _kuzu_conn = store.get_kuzu_connection()
    if _kuzu_conn is None:
        print("  ⚠️  GraphStore 使用 NetworkX 後端，跳過 KuzuContextExtractor 驗證")
    else:
        extractor = KuzuContextExtractor(_kuzu_conn)
        for entity in sample_entities:
            ctx = extractor.extract_context(entity)
            status = "✅" if ctx.total_paths > 0 else "⚠️ "
            print(f"  {status} {entity}: {len(ctx.one_hop_paths)} 1-hop + "
                  f"{len(ctx.two_hop_paths)} 2-hop")
except Exception as exc:
    print(f"  ⚠️  KuzuContextExtractor 驗證失敗: {exc}")

print("\n" + "=" * 60)
print("checkg.py 完成！若實體/邊數量符合預期，後端API查KG即可有結果。")
print(f"📂 DB 文件: {_DB_PATH}")
print("=" * 60)
