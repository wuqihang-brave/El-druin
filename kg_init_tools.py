#!/usr/bin/env python3
"""
kg_init_tools.py – 一鍵KG初始化工具

支持：
1. 查看當前 KG 狀態（實體/邊數量 + 物理路徑）
2. 批量導入業務實體與關係（等同 checkg.py 的批量寫入部分）
3. 清空並重建 KG（危險！僅用於測試重置）

用法（從項目根目錄運行）：
    PYTHONPATH=backend python kg_init_tools.py status
    PYTHONPATH=backend python kg_init_tools.py populate
    PYTHONPATH=backend python kg_init_tools.py reset
    PYTHONPATH=backend python kg_init_tools.py reset --yes   # 跳過確認
"""

from __future__ import annotations

import sys
import os
import argparse

# ── 確保 backend/ 在 Python 搜索路徑中 ──────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_HERE, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# ── 核心業務數據 ──────────────────────────────────────────────────────────────

BUSINESS_ENTITIES = [
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

BUSINESS_RELATIONS = [
    # (from_name, from_type, to_name, to_type, relation_type, weight)
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


# ── 工具函數 ──────────────────────────────────────────────────────────────────

def _get_db_path() -> str:
    """Return the KuzuDB file path from settings (already absolute after config.py fix)."""
    from app.core.config import get_settings
    return get_settings().kuzu_db_path


def cmd_status() -> None:
    """Print current KG status: entity/edge counts and physical path."""
    db_path = _get_db_path()
    print(f"📂 KuzuDB 物理路徑: {db_path}")
    print(f"   文件存在: {'✅ 是' if os.path.exists(db_path) else '❌ 否（未初始化）'}")

    from app.knowledge.graph_store import GraphStore
    store = GraphStore()
    entities = store.get_entities(1000)
    relations = store.get_relations(2000)
    stats = store.stats() if hasattr(store, "stats") else {}

    print(f"\n當前 KG 統計：")
    print(f"  實體數量: {len(entities)}")
    print(f"  邊數量:   {len(relations)}")
    if stats:
        for k, v in stats.items():
            print(f"  {k}: {v}")

    if entities:
        print(f"\n樣本實體（前10）：")
        for e in entities[:10]:
            print(f"  - {e.get('name', '')} ({e.get('type', '')})")

    # Verify key business entities
    business_names = {name for name, _ in BUSINESS_ENTITIES}
    found = {e["name"] for e in entities if e.get("name") in business_names}
    missing = business_names - found
    print(f"\n業務實體覆蓋：{len(found)}/{len(business_names)}")
    if missing:
        print(f"  缺失業務實體（共 {len(missing)} 個，運行 'populate' 命令補全）：")
        for name in sorted(missing)[:10]:
            print(f"    - {name}")
        if len(missing) > 10:
            print(f"    ... 及 {len(missing) - 10} 個更多")


def cmd_populate() -> None:
    """Write all business entities and relations into the KG."""
    db_path = _get_db_path()
    print(f"📂 寫入目標 KuzuDB: {db_path}")

    from app.knowledge.graph_store import GraphStore
    store = GraphStore()

    print(f"寫入 {len(BUSINESS_ENTITIES)} 個業務實體...")
    for name, etype in BUSINESS_ENTITIES:
        store.add_entity(name, etype)

    print(f"寫入 {len(BUSINESS_RELATIONS)} 條業務關係...")
    for f, ft, t, tt, r, w in BUSINESS_RELATIONS:
        store.add_relation(f, ft, t, tt, r, w)

    entities = store.get_entities(1000)
    relations = store.get_relations(2000)
    print(f"\n✅ 寫入完成！")
    print(f"   當前實體數量: {len(entities)}")
    print(f"   當前邊數量:   {len(relations)}")

    # Quick sanity check with KuzuContextExtractor (reuse GraphStore connection)
    print("\n驗證關鍵實體 1-hop + 2-hop 路徑：")
    try:
        from ontology.kuzu_context_extractor import KuzuContextExtractor
        _kuzu_conn = store.get_kuzu_connection()
        if _kuzu_conn is None:
            print("  ⚠️  GraphStore 使用 NetworkX 後端，跳過路徑驗證")
        else:
            extractor = KuzuContextExtractor(_kuzu_conn)
            sample = ["United States", "China", "United Nations", "Syria"]
            for entity in sample:
                ctx = extractor.extract_context(entity)
                status = "✅" if ctx.total_paths > 0 else "⚠️ "
                print(f"  {status} {entity}: {len(ctx.one_hop_paths)} 1-hop + "
                      f"{len(ctx.two_hop_paths)} 2-hop")
    except Exception as exc:
        print(f"  路徑驗證跳過: {exc}")


def cmd_reset(yes: bool = False) -> None:
    """Delete and recreate the KuzuDB file (destructive – for testing only)."""
    db_path = _get_db_path()
    print(f"⚠️  即將清空並重建 KuzuDB: {db_path}")
    if not yes:
        answer = input("確認清空？輸入 'yes' 確認，其他任意鍵取消: ").strip()
        if answer.lower() != "yes":
            print("已取消。")
            return

    import shutil
    if os.path.isdir(db_path):
        shutil.rmtree(db_path, ignore_errors=True)
        print(f"✅ 已刪除目錄: {db_path}")
    elif os.path.isfile(db_path):
        os.remove(db_path)
        print(f"✅ 已刪除文件: {db_path}")
    else:
        print(f"路徑不存在，跳過刪除: {db_path}")

    print("重建 KG 並批量導入業務數據...")
    cmd_populate()


# ── CLI 入口 ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="El-druin 知識圖譜初始化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令：
  status    查看當前 KG 狀態（實體/邊數量 + 物理路徑）
  populate  批量導入核心業務實體與關係
  reset     清空並重建 KG（危險，僅用於測試！）

示例：
  PYTHONPATH=backend python kg_init_tools.py status
  PYTHONPATH=backend python kg_init_tools.py populate
  PYTHONPATH=backend python kg_init_tools.py reset --yes
""",
    )
    parser.add_argument(
        "command",
        choices=["status", "populate", "reset"],
        help="要執行的命令",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="跳過 reset 命令的確認提示",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"kg_init_tools.py – 命令: {args.command}")
    print("=" * 60)

    if args.command == "status":
        cmd_status()
    elif args.command == "populate":
        cmd_populate()
    elif args.command == "reset":
        cmd_reset(yes=args.yes)

    print("\n完成！")


if __name__ == "__main__":
    main()
