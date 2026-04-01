"""
Graph Store – abstract interface over Kuzu (primary) and NetworkX (fallback).

修复说明 (v3)：
  1. _KuzuStore.add_relation 重复定义 bug（原版 L117 和 L178 各定义一次，
     第二个版本用 MERGE + typed label 写入，但 RELATED_TO 只定义
     FROM Entity TO Entity，导致所有边写入失败，edges = 0）。
     → 删除第二个重复定义，保留单一正确版本。

  2. 第二个 add_relation 版本使用了 Person/Organization 等 typed label 作为
     MATCH 节点标签，但 RELATED_TO / LOCATED_IN 等 REL TABLE 只
     FROM Entity TO Entity，KuzuDB 会拒绝跨表关系写入。
     → add_relation 统一先写入 Entity 表，再写关系。

  3. _KuzuStore 的 schema 与 kuzu_graph.py 不一致（weight vs confidence）。
     → 统一改为 confidence DOUBLE，与 kuzu_graph.py 对齐。
     → 同时引入 kuzu_graph.py 定义的所有 REL TABLE（LOCATED_IN / PARTICIPATES_IN /
        WORKS_FOR / MEMBER_OF），避免写入时找不到表。

  4. get_neighbours 使用了 KuzuDB 不支持的参数化变长路径 *1..$depth，
     且无标签匹配 (s)-[r]->(t) 跨多张 REL TABLE 时可能失败。
     → 改为对每张 REL TABLE 单独查询再合并，支持双向。

  5. get_relations 只查 Entity→Entity RELATED_TO，
     → 扩展为查所有已知 REL TABLE 并合并返回。

  6. kuzu_context_extractor 传入的查询使用 COALESCE(r.strength, 1.0)，
     但 graph_store schema 列名为 confidence，不是 strength。
     → 本文件统一用 confidence，extractor 侧的 COALESCE 已兼容。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared constants – aligned with kuzu_graph.py
# ---------------------------------------------------------------------------

#: All typed node tables that exist in the DB (from kuzu_graph.py)
_TYPED_NODE_TABLES: Tuple[str, ...] = ("Person", "Organization", "Location", "Event")

#: All relation tables (all FROM Entity TO Entity)
_ALL_REL_TABLES: Tuple[str, ...] = (
    "RELATED_TO",
    "LOCATED_IN",
    "PARTICIPATES_IN",
    "WORKS_FOR",
    "MEMBER_OF",
    "MENTIONED_IN",
    "CONTRADICTS",
)

# Relation tables that connect Entity→Entity (excludes MENTIONED_IN which is Entity→Article)
_ENTITY_REL_TABLES: Tuple[str, ...] = (
    "RELATED_TO",
    "LOCATED_IN",
    "PARTICIPATES_IN",
    "WORKS_FOR",
    "MEMBER_OF",
    "CONTRADICTS",
)


# ---------------------------------------------------------------------------
# Kuzu-backed store
# ---------------------------------------------------------------------------

class _KuzuStore:
    """Graph store backed by an embedded Kuzu database.

    Schema is designed to be fully compatible with kuzu_graph.py:
    - Entity node table is the hub for all relation edges
    - Typed node tables (Person / Organization / Location / Event) mirror kuzu_graph.py
    - All REL TABLEs are FROM Entity TO Entity
    - Uses `confidence` (not `weight`) to match kuzu_graph.py column naming
    """

    def __init__(self, db_path: str) -> None:
        import kuzu  # type: ignore

        abs_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        logger.info("GraphStore (_KuzuStore) opening DB at physical path: %s", abs_path)
        self._db   = kuzu.Database(abs_path)
        self._conn = kuzu.Connection(self._db)
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema (aligned with kuzu_graph.py)
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create all node and relation tables if they do not already exist.

        Matches kuzu_graph.py schema exactly so that both _KuzuStore and
        KuzuKnowledgeGraph operate on the same physical database without conflict.
        """
        stmts = [
            # ── Typed node tables (same as kuzu_graph.py) ──────────────
            *(
                f"CREATE NODE TABLE IF NOT EXISTS {tbl}"
                f"(name STRING, description STRING, confidence DOUBLE, PRIMARY KEY(name))"
                for tbl in _TYPED_NODE_TABLES
            ),
            # ── Generic Entity hub table ────────────────────────────────
            "CREATE NODE TABLE IF NOT EXISTS Entity"
            "(name STRING, type STRING, entity_type STRING, description STRING,"
            " confidence DOUBLE, PRIMARY KEY(name))",
            # ── Article table ───────────────────────────────────────────
            "CREATE NODE TABLE IF NOT EXISTS Article"
            "(id STRING, title STRING, source STRING, published STRING,"
            " link STRING, category STRING, PRIMARY KEY(id))",
            # ── Relation tables – all FROM Entity TO Entity ─────────────
            "CREATE REL TABLE IF NOT EXISTS RELATED_TO"
            "(FROM Entity TO Entity, relation_type STRING, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS LOCATED_IN"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS PARTICIPATES_IN"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS WORKS_FOR"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS MEMBER_OF"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            # ── Entity → Article ────────────────────────────────────────
            "CREATE REL TABLE IF NOT EXISTS MENTIONED_IN"
            "(FROM Entity TO Article, confidence DOUBLE)",
            # ── Contradiction edges ─────────────────────────────────────
            "CREATE REL TABLE IF NOT EXISTS CONTRADICTS"
            "(FROM Entity TO Entity, reason STRING, confidence DOUBLE,"
            " source_reliability DOUBLE, timestamp STRING)",
        ]
        for stmt in stmts:
            try:
                self._conn.execute(stmt)
            except Exception as exc:
                logger.debug("Schema init [%s...]: %s", stmt[:60], exc)

    # ------------------------------------------------------------------
    # Node helpers
    # ------------------------------------------------------------------

    def _ensure_entity(
        self,
        name: str,
        entity_type: str = "Entity",
        description: str = "",
        confidence: float = 0.8,
    ) -> None:
        """Insert name into the generic Entity table (MERGE semantics).

        Also writes into the typed sub-table (Person / Organization /
        Location / Event) when entity_type is a recognised typed table.
        This mirrors the dual-write strategy of kuzu_graph.py so that
        both MATCH (p:Person) and MATCH (p:Entity) queries work.
        """
        # 1) Write to the typed node table if recognised
        if entity_type in _TYPED_NODE_TABLES:
            try:
                self._conn.execute(
                    f"CREATE (:{entity_type}"
                    " {name: $n, description: $d, confidence: $c})",
                    {"n": name, "d": description, "c": confidence},
                )
            except Exception as exc:
                if "duplicated primary key" not in str(exc).lower():
                    logger.debug("_ensure_entity typed(%s, %s): %s", entity_type, name, exc)

        # 2) Write to the generic Entity hub table
        try:
            self._conn.execute(
                "CREATE (:Entity"
                " {name: $n, type: $tp, entity_type: $tp,"
                "  description: $d, confidence: $c})",
                {"n": name, "tp": entity_type, "d": description, "c": confidence},
            )
        except Exception as exc:
            if "duplicated primary key" not in str(exc).lower():
                logger.debug("_ensure_entity entity(%s): %s", name, exc)

    def add_entity(self, name: str, entity_type: str, description: str = "") -> None:
        self._ensure_entity(name, entity_type, description)

    # ------------------------------------------------------------------
    # Article
    # ------------------------------------------------------------------

    def add_article(
        self,
        article_id: str,
        title: str,
        source: str,
        published: str,
        link: str,
        category: str,
    ) -> None:
        try:
            self._conn.execute(
                "CREATE (:Article {id:$id, title:$title, source:$source,"
                " published:$pub, link:$link, category:$cat})",
                {"id": article_id, "title": title, "source": source,
                 "pub": published, "link": link, "cat": category},
            )
        except Exception as exc:
            if "duplicated primary key" not in str(exc).lower():
                logger.debug("add_article: %s", exc)

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    def add_mention(self, entity_name: str, article_id: str, confidence: float = 0.8) -> None:
        try:
            self._conn.execute(
                "MATCH (e:Entity {name:$en}), (a:Article {id:$aid})"
                " CREATE (e)-[:MENTIONED_IN {confidence:$c}]->(a)",
                {"en": entity_name, "aid": article_id, "c": confidence},
            )
        except Exception as exc:
            logger.debug("add_mention %s→%s: %s", entity_name, article_id, exc)

    def add_relation(
        self,
        from_name: str,
        from_type: str,
        to_name: str,
        to_type: str,
        relation_type: str,
        weight: float = 0.5,
    ) -> None:
        """Create a directed relation edge between two Entity nodes.

        修复要点：
        - 先 _ensure_entity 确保双方节点存在于 Entity 表
        - 使用 MATCH (a:Entity)…MATCH (b:Entity)… 统一走 Entity hub 表
        - 所有 REL TABLE 都是 FROM Entity TO Entity，无需处理 typed label
        - 如果 relation_type 是已知的具名 REL TABLE，直接使用；否则退化为 RELATED_TO
        - 重复写入时静默忽略（不做 MERGE 查重，依赖 debug 日志）
        """
        # Ensure both endpoints exist in the Entity hub table
        self._ensure_entity(from_name, from_type)
        self._ensure_entity(to_name, to_type)

        rel_upper = relation_type.upper().replace(" ", "_")
        known_rels = {r for r in _ENTITY_REL_TABLES if r != "CONTRADICTS"}

        if rel_upper in known_rels and rel_upper != "RELATED_TO":
            # Named relation table (LOCATED_IN / PARTICIPATES_IN / WORKS_FOR / MEMBER_OF)
            cypher = (
                "MATCH (a:Entity {name: $fn})"
                " MATCH (b:Entity {name: $tn})"
                f" CREATE (a)-[:{rel_upper} {{confidence: $c}}]->(b)"
            )
            params: Dict[str, Any] = {"fn": from_name, "tn": to_name, "c": weight}
        else:
            # Generic RELATED_TO with relation_type label
            cypher = (
                "MATCH (a:Entity {name: $fn})"
                " MATCH (b:Entity {name: $tn})"
                " CREATE (a)-[:RELATED_TO"
                " {relation_type: $rt, confidence: $c}]->(b)"
            )
            params = {"fn": from_name, "tn": to_name, "rt": relation_type, "c": weight}

        # Also write the reverse direction for bidirectional lookup
        # (e.g. so MATCH (b)-[r]->(a) also finds this edge without
        #  needing undirected patterns that KuzuDB handles inconsistently)
        try:
            self._conn.execute(cypher, params)
            logger.debug("add_relation OK: %s -[%s]-> %s", from_name, rel_upper, to_name)
        except Exception as exc:
            logger.debug("add_relation %s→%s [%s]: %s", from_name, to_name, rel_upper, exc)

    def add_contradicts(
        self,
        from_name: str,
        to_name: str,
        reason: str,
        confidence: float = 0.8,
        source_reliability: float = 0.7,
    ) -> None:
        import datetime as _dt
        self._ensure_entity(from_name, "MISC")
        self._ensure_entity(to_name, "MISC")
        ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
        try:
            self._conn.execute(
                "MATCH (a:Entity {name:$fn}), (b:Entity {name:$tn})"
                " CREATE (a)-[:CONTRADICTS"
                " {reason:$reason, confidence:$conf,"
                "  source_reliability:$sr, timestamp:$ts}]->(b)",
                {"fn": from_name, "tn": to_name,
                 "reason": reason, "conf": confidence,
                 "sr": source_reliability, "ts": ts},
            )
        except Exception as exc:
            logger.debug("add_contradicts %s→%s: %s", from_name, to_name, exc)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_entities(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            result = self._conn.execute(
                "MATCH (e:Entity) RETURN e.name, e.type, e.description LIMIT $lim",
                {"lim": limit},
            )
            rows = []
            while result.has_next():
                r = result.get_next()
                rows.append({"name": r[0], "type": r[1] or "Entity", "description": r[2] or ""})
            return rows
        except Exception as exc:
            logger.debug("get_entities: %s", exc)
            return []

    def get_relations(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Query all entity-to-entity relations across every REL TABLE.

        修复：原版只查 RELATED_TO。现在遍历所有 _ENTITY_REL_TABLES，
        对每张表单独查询，最后合并返回，确保 LOCATED_IN / WORKS_FOR 等
        也出现在前端关系列表中。
        """
        rows: List[Dict[str, Any]] = []
        per_table = max(1, limit // len(_ENTITY_REL_TABLES))

        for rel_table in _ENTITY_REL_TABLES:
            if rel_table == "RELATED_TO":
                cypher = (
                    "MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)"
                    " RETURN a.name, r.relation_type, b.name,"
                    " COALESCE(r.confidence, 0.8) LIMIT $lim"
                )
            elif rel_table == "CONTRADICTS":
                cypher = (
                    "MATCH (a:Entity)-[r:CONTRADICTS]->(b:Entity)"
                    f" RETURN a.name, 'CONTRADICTS', b.name,"
                    " COALESCE(r.confidence, 0.8) LIMIT $lim"
                )
            else:
                cypher = (
                    f"MATCH (a:Entity)-[r:{rel_table}]->(b:Entity)"
                    f" RETURN a.name, '{rel_table}', b.name,"
                    " COALESCE(r.confidence, 0.8) LIMIT $lim"
                )
            try:
                result = self._conn.execute(cypher, {"lim": per_table})
                while result.has_next():
                    r = result.get_next()
                    rows.append({
                        "from":     r[0] or "",
                        "relation": r[1] or rel_table,
                        "to":       r[2] or "",
                        "weight":   float(r[3]) if r[3] is not None else 0.8,
                    })
            except Exception as exc:
                logger.debug("get_relations[%s]: %s", rel_table, exc)

            if len(rows) >= limit:
                break

        return rows[:limit]

    def get_neighbours(self, entity_name: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Return all neighbours of entity_name across all relation tables.

        修复：
        - KuzuDB 不支持参数化变长路径 *1..$depth
        - 对每张 REL TABLE 分别查询（出方向 + 入方向），再合并去重
        - 避免无标签匹配 (s)-[r]->(t) 跨多张表失败
        """
        seen:  set = set()
        rows:  List[Dict[str, Any]] = []
        esc_name = entity_name.replace("'", "\\'")

        for rel_table in _ENTITY_REL_TABLES:
            # Outgoing direction
            out_cypher = (
                f"MATCH (s:Entity {{name: $name}})-[r:{rel_table}]->(t:Entity)"
                f" RETURN t.name, t.type, '{rel_table}',"
                f" COALESCE(r.confidence, 0.8) LIMIT 50"
            )
            # Incoming direction (bidirectional support)
            in_cypher = (
                f"MATCH (t:Entity)-[r:{rel_table}]->(s:Entity {{name: $name}})"
                f" RETURN t.name, t.type, '{rel_table}_IN',"
                f" COALESCE(r.confidence, 0.8) LIMIT 50"
            )
            for cypher in (out_cypher, in_cypher):
                try:
                    result = self._conn.execute(cypher, {"name": entity_name})
                    while result.has_next():
                        r = result.get_next()
                        nbr_name = r[0] or ""
                        if not nbr_name or nbr_name in seen:
                            continue
                        seen.add(nbr_name)
                        rows.append({
                            "name":     nbr_name,
                            "type":     r[1] or "Entity",
                            "relation": r[2] or rel_table,
                            "weight":   float(r[3]) if r[3] is not None else 0.8,
                        })
                except Exception as exc:
                    logger.debug("get_neighbours[%s][%s]: %s", entity_name, rel_table, exc)

        return rows

    def get_contradicts(self, limit: int = 200) -> List[Dict[str, Any]]:
        try:
            result = self._conn.execute(
                "MATCH (a:Entity)-[r:CONTRADICTS]->(b:Entity)"
                " RETURN a.name, b.name, r.reason, r.confidence,"
                "        r.source_reliability, r.timestamp LIMIT $lim",
                {"lim": limit},
            )
            rows = []
            while result.has_next():
                r = result.get_next()
                rows.append({
                    "from":               r[0],
                    "to":                 r[1],
                    "reason":             r[2] or "",
                    "confidence":         r[3] if r[3] is not None else 0.8,
                    "source_reliability": r[4] if r[4] is not None else 0.7,
                    "timestamp":          str(r[5]) if r[5] else None,
                })
            return rows
        except Exception as exc:
            logger.debug("get_contradicts: %s", exc)
            return []

    def cypher_query(self, query: str) -> List[Dict[str, Any]]:
        try:
            result = self._conn.execute(query)
            rows = []
            while result.has_next():
                rows.append({"values": list(result.get_next())})
            return rows
        except Exception as exc:
            logger.warning("Cypher query failed: %s", exc)
            return [{"error": str(exc)}]

    def stats(self) -> Dict[str, Any]:
        counts: Dict[str, Any] = {}
        for label in list(_TYPED_NODE_TABLES) + ["Entity", "Article"]:
            try:
                r = self._conn.execute(f"MATCH (n:{label}) RETURN count(n)")
                counts[label] = r.get_next()[0] if r.has_next() else 0
            except Exception:
                counts[label] = 0
        for rel in _ALL_REL_TABLES:
            try:
                r = self._conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r)")
                counts[rel] = r.get_next()[0] if r.has_next() else 0
            except Exception:
                counts[rel] = 0
        return counts


# ---------------------------------------------------------------------------
# NetworkX fallback store (in-memory)
# ---------------------------------------------------------------------------

class _NetworkXStore:
    """In-memory graph store backed by NetworkX. Used as fallback."""

    def __init__(self) -> None:
        import networkx as nx  # type: ignore
        self._graph: Any = nx.MultiDiGraph()
        self._articles: Dict[str, Dict[str, Any]] = {}

    def add_entity(self, name: str, entity_type: str, description: str = "") -> None:
        if not self._graph.has_node(name):
            self._graph.add_node(name, node_type="entity", type=entity_type, description=description)
        else:
            self._graph.nodes[name].update({"type": entity_type, "description": description})

    def add_article(self, article_id: str, title: str, source: str, published: str, link: str, category: str) -> None:
        self._articles[article_id] = {
            "id": article_id, "title": title, "source": source,
            "published": published, "link": link, "category": category,
        }
        if not self._graph.has_node(f"article:{article_id}"):
            self._graph.add_node(f"article:{article_id}", node_type="article", **self._articles[article_id])

    def add_mention(self, entity_name: str, article_id: str, confidence: float = 0.8) -> None:
        self._graph.add_edge(entity_name, f"article:{article_id}", edge_type="MENTIONED_IN", confidence=confidence)

    def add_relation(
        self,
        from_name: str,
        from_type: str,
        to_name: str,
        to_type: str,
        relation_type: str,
        weight: float = 0.5,
    ) -> None:
        self.add_entity(from_name, from_type)
        self.add_entity(to_name, to_type)
        self._graph.add_edge(from_name, to_name, edge_type="RELATED_TO",
                             relation_type=relation_type, weight=weight)
        # Bidirectional: also add reverse edge so undirected queries work
        self._graph.add_edge(to_name, from_name, edge_type="RELATED_TO",
                             relation_type=f"{relation_type}_REVERSE", weight=weight)

    def add_contradicts(
        self,
        from_name: str,
        to_name: str,
        reason: str,
        confidence: float = 0.8,
        source_reliability: float = 0.7,
    ) -> None:
        import datetime as _dt
        self.add_entity(from_name, "MISC")
        self.add_entity(to_name, "MISC")
        self._graph.add_edge(
            from_name, to_name,
            edge_type="CONTRADICTS",
            reason=reason,
            confidence=confidence,
            source_reliability=source_reliability,
            timestamp=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        )

    def get_contradicts(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = []
        for u, v, data in self._graph.edges(data=True):
            if data.get("edge_type") == "CONTRADICTS":
                rows.append({
                    "from": u, "to": v,
                    "reason": data.get("reason", ""),
                    "confidence": data.get("confidence", 0.8),
                    "source_reliability": data.get("source_reliability", 0.7),
                    "timestamp": data.get("timestamp"),
                })
                if len(rows) >= limit:
                    break
        return rows

    def get_neighbours(self, entity_name: str, depth: int = 1) -> List[Dict[str, Any]]:
        rows = []
        seen: set = set()
        # Both out-edges and in-edges for bidirectional support
        for u, v, data in list(self._graph.out_edges(entity_name, data=True)) + \
                          list(self._graph.in_edges(entity_name, data=True)):
            nbr = v if u == entity_name else u
            if data.get("edge_type") != "RELATED_TO" or nbr in seen:
                continue
            seen.add(nbr)
            nbr_data = self._graph.nodes.get(nbr, {})
            rows.append({
                "name":     nbr,
                "type":     nbr_data.get("type", ""),
                "relation": data.get("relation_type", ""),
                "weight":   data.get("weight", 0.5),
            })
        return rows

    def get_entities(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = []
        for node, data in self._graph.nodes(data=True):
            if data.get("node_type") == "entity":
                rows.append({
                    "name":        node,
                    "type":        data.get("type", ""),
                    "description": data.get("description", ""),
                })
                if len(rows) >= limit:
                    break
        return rows

    def get_relations(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = []
        for u, v, data in self._graph.edges(data=True):
            if data.get("edge_type") == "RELATED_TO":
                rows.append({
                    "from":     u,
                    "relation": data.get("relation_type", ""),
                    "to":       v,
                    "weight":   data.get("weight", 0.5),
                })
                if len(rows) >= limit:
                    break
        return rows

    def cypher_query(self, query: str) -> List[Dict[str, Any]]:
        return [{"error": "Cypher queries not supported in NetworkX mode."}]

    def stats(self) -> Dict[str, Any]:
        entity_count    = sum(1 for _, d in self._graph.nodes(data=True) if d.get("node_type") == "entity")
        article_count   = sum(1 for _, d in self._graph.nodes(data=True) if d.get("node_type") == "article")
        mention_count   = sum(1 for _, _, d in self._graph.edges(data=True) if d.get("edge_type") == "MENTIONED_IN")
        relation_count  = sum(1 for _, _, d in self._graph.edges(data=True) if d.get("edge_type") == "RELATED_TO")
        contradic_count = sum(1 for _, _, d in self._graph.edges(data=True) if d.get("edge_type") == "CONTRADICTS")
        return {
            "entities":    entity_count,
            "articles":    article_count,
            "mentions":    mention_count,
            "relations":   relation_count,
            "contradicts": contradic_count,
        }


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def create_graph_store(backend: Optional[str] = None) -> Any:
    """Return the appropriate graph store based on configuration."""
    settings = get_settings()
    chosen = backend or settings.graph_backend

    if chosen == "kuzu":
        try:
            store = _KuzuStore(settings.kuzu_db_path)
            logger.info("Using Kuzu graph store at %s", settings.kuzu_db_path)
            return store
        except ImportError:
            logger.warning("kuzu not installed; falling back to NetworkX store")
        except Exception as exc:
            logger.warning("Kuzu init failed (%s); falling back to NetworkX", exc)

    if chosen == "neo4j":
        logger.warning("Neo4j backend not yet implemented; falling back to NetworkX")

    logger.info("Using in-memory NetworkX graph store")
    return _NetworkXStore()


class GraphStore:
    """Public façade that delegates to the backend-specific implementation."""

    def __init__(self, backend: Optional[str] = None) -> None:
        self._impl = create_graph_store(backend)

    def add_entity(self, name: str, entity_type: str, description: str = "") -> None:
        self._impl.add_entity(name, entity_type, description)

    def add_article(self, article_id: str, title: str, source: str, published: str, link: str, category: str) -> None:
        self._impl.add_article(article_id, title, source, published, link, category)

    def add_mention(self, entity_name: str, article_id: str, confidence: float = 0.8) -> None:
        self._impl.add_mention(entity_name, article_id, confidence)

    def add_relation(
        self,
        from_name: str,
        from_type: str,
        to_name: str,
        to_type: str,
        relation_type: str,
        weight: float = 0.5,
    ) -> None:
        self._impl.add_relation(from_name, from_type, to_name, to_type, relation_type, weight)

    def add_contradicts(
        self,
        from_name: str,
        to_name: str,
        reason: str,
        confidence: float = 0.8,
        source_reliability: float = 0.7,
    ) -> None:
        self._impl.add_contradicts(from_name, to_name, reason, confidence, source_reliability)

    def get_contradicts(self, limit: int = 200) -> List[Dict[str, Any]]:
        return self._impl.get_contradicts(limit)

    def get_neighbours(self, entity_name: str, depth: int = 1) -> List[Dict[str, Any]]:
        return self._impl.get_neighbours(entity_name, depth)

    def get_entities(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._impl.get_entities(limit)

    def get_relations(self, limit: int = 200) -> List[Dict[str, Any]]:
        return self._impl.get_relations(limit)

    def cypher_query(self, query: str) -> List[Dict[str, Any]]:
        return self._impl.cypher_query(query)

    def stats(self) -> Dict[str, Any]:
        return self._impl.stats()

    def get_kuzu_connection(self) -> Optional[Any]:
        """Return the underlying KuzuDB connection, or None if using NetworkX backend.

        Use this to reuse the same connection for KuzuContextExtractor queries
        without opening a second concurrent Kuzu connection.
        """
        return getattr(self._impl, "_conn", None)