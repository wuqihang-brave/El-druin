"""
Ontological Context Extraction from KuzuDB

核心逻辑：从知识图谱提取"本体路径"作为 LLM 推理的绝对前提

修复说明 (v2)：
  1. _get_one_hop_paths / _get_two_hop_paths
     原版将 type_filter（含 AND）直接拼入 MATCH 节点模式中间，
     KuzuDB 不支持这种写法，会抛出 BinderException。
     修复：改用独立的 WHERE 子句，放在完整 MATCH 模式之后。

  2. r.strength / r1.strength / r2.strength
     并非每张边表都有 strength 属性，直接引用会触发 BinderException。
     修复：改用 COALESCE(r.strength, 1.0) 安全回退。

  3. target_role / target_virtue
     原版在 _get_one_hop_paths 中查询了 b.role / b.virtue，
     但这两个属性在通用节点表中并不保证存在。
     修复：不在 SELECT 中查询这两列，统一设为 None，
     避免 BinderException: Cannot find property role for b。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import kuzu  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class RelationshipPath:
    """Single ontological relationship path."""

    hop: int  # 1 or 2
    source_entity: str
    source_type: str
    relation_type: str
    target_entity: str
    target_type: str
    target_virtue: Optional[str] = None
    target_role: Optional[str] = None
    second_relation: Optional[str] = None
    third_entity: Optional[str] = None
    strength: float = 1.0

    def to_text(self) -> str:
        """Convert to natural language path description."""
        text = (
            f"[{self.source_entity}:{self.source_type}]"
            f" --{self.relation_type}-->"
            f" [{self.target_entity}:{self.target_type}"
        )
        if self.target_virtue:
            text += f" (德:{self.target_virtue})"
        if self.target_role:
            text += f" (角:{self.target_role})"
        text += "]"
        if self.second_relation and self.third_entity:
            text += f" --{self.second_relation}--> [{self.third_entity}]"
        return text


@dataclass
class OntologicalContext:
    """Complete ontological context for an entity."""

    seed_entity: str
    seed_type: str
    extraction_time: str
    one_hop_paths: List[RelationshipPath] = field(default_factory=list)
    two_hop_paths: List[RelationshipPath] = field(default_factory=list)
    total_paths: int = 0

    def to_prompt_context(self) -> str:
        """Convert to LLM-ready prompt string."""
        context = (
            f"\n【本体路径上下文】\n"
            f"中心实体: {self.seed_entity} ({self.seed_type})\n"
            f"提取时间: {self.extraction_time}\n"
            f"总关系数: {self.total_paths}\n"
            f"\n【一阶关系 (Direct Relations)】\n"
        )
        for path in self.one_hop_paths[:5]:
            context += f"  • {path.to_text()}\n"

        context += "\n【二阶关系 (Secondary Relations)】\n"
        for path in self.two_hop_paths[:5]:
            context += f"  • {path.to_text()}\n"

        return context


class KuzuContextExtractor:
    """Extract ontological context from KuzuDB for LLM grounding."""

    def __init__(self, kuzu_conn: kuzu.Connection) -> None:
        self.conn = kuzu_conn

    def extract_context(
        self,
        seed_entity_name: str,
        entity_type: Optional[str] = None,
        max_depth: int = 2,
        limit_per_hop: int = 10,
    ) -> OntologicalContext:
        """Extract 1-hop and 2-hop ontological paths for a seed entity."""
        try:
            one_hop = self._get_one_hop_paths(seed_entity_name, entity_type, limit_per_hop)
            two_hop: List[RelationshipPath] = []
            if max_depth >= 2:
                two_hop = self._get_two_hop_paths(seed_entity_name, entity_type, limit_per_hop)

            context = OntologicalContext(
                seed_entity=seed_entity_name,
                seed_type=entity_type or "UNKNOWN",
                extraction_time=datetime.now().isoformat(),
                one_hop_paths=one_hop,
                two_hop_paths=two_hop,
                total_paths=len(one_hop) + len(two_hop),
            )
            logger.info(
                "Extracted ontological context for %s: %d 1-hop + %d 2-hop paths",
                seed_entity_name, len(one_hop), len(two_hop),
            )
            return context

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to extract context for %s: %s", seed_entity_name, exc)
            return OntologicalContext(
                seed_entity=seed_entity_name,
                seed_type=entity_type or "UNKNOWN",
                extraction_time=datetime.now().isoformat(),
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    # All relation tables defined in kuzu_graph.py / graph_store.py
    _ENTITY_REL_TABLES = (
        "RELATED_TO",
        "LOCATED_IN",
        "PARTICIPATES_IN",
        "WORKS_FOR",
        "MEMBER_OF",
        "CONTRADICTS",
    )

    def _get_one_hop_paths(
        self,
        seed_entity: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[RelationshipPath]:
        """Get direct relationships from seed entity.

        修复要点（v3）：
        - KuzuDB 不支持跨多张 REL TABLE 的无标签匹配 MATCH (a)-[r]->(b)
          当各 REL TABLE schema 不同时（例如 RELATED_TO 有 relation_type 列，
          LOCATED_IN 没有），KuzuDB 会抛出 BinderException。
        - 解决方案：对每张 REL TABLE 单独发一条查询，再合并结果。
        - 列名统一用 confidence（与 kuzu_graph.py / graph_store.py 对齐）。
        - WHERE 子句独立放在完整 MATCH 模式后。
        """
        paths: List[RelationshipPath] = []
        esc = self._escape_cypher(seed_entity)
        per_table = max(1, limit // len(self._ENTITY_REL_TABLES))

        for rel_table in self._ENTITY_REL_TABLES:
            try:
                where = f"a.name = '{esc}'"
                if entity_type:
                    where += f" AND a.type = '{self._escape_cypher(entity_type)}'"

                if rel_table == "RELATED_TO":
                    query = (
                        f"MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)"
                        f" WHERE {where}"
                        f" RETURN a.name, a.type, 'RELATED_TO',"
                        f"  b.name, b.type, COALESCE(r.confidence, 0.8)"
                        f" LIMIT {per_table}"
                    )
                else:
                    query = (
                        f"MATCH (a:Entity)-[r:{rel_table}]->(b:Entity)"
                        f" WHERE {where}"
                        f" RETURN a.name, a.type, '{rel_table}',"
                        f"  b.name, b.type, COALESCE(r.confidence, 0.8)"
                        f" LIMIT {per_table}"
                    )

                result = self.conn.execute(query)
                while result.has_next():
                    row = result.get_next()
                    paths.append(RelationshipPath(
                        hop=1,
                        source_entity=row[0] or seed_entity,
                        source_type=row[1] or "UNKNOWN",
                        relation_type=row[2] or rel_table,
                        target_entity=row[3] or "",
                        target_type=row[4] or "UNKNOWN",
                        target_role=None,
                        target_virtue=None,
                        strength=float(row[5]) if row[5] is not None else 0.8,
                    ))
            except Exception as exc:  # noqa: BLE001
                logger.debug("1-hop[%s] for %s: %s", rel_table, seed_entity, exc)

        logger.debug("Found %d 1-hop paths for %s", len(paths), seed_entity)
        return paths[:limit]

    def _get_two_hop_paths(
        self,
        seed_entity: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[RelationshipPath]:
        """Get secondary relationships (entity -> intermediate -> target).

        修复要点（v3）：
        - 同 _get_one_hop_paths，不使用无标签 MATCH (a)-[r1]->(b)-[r2]->(c)
        - 按 REL TABLE 逐一查询，避免跨表 schema 不一致导致 BinderException
        - 使用 confidence 列名与 schema 对齐
        """
        paths: List[RelationshipPath] = []
        esc = self._escape_cypher(seed_entity)

        # 2-hop queries: first hop from each rel table, second hop always RELATED_TO
        two_hop_combos = [("RELATED_TO", "RELATED_TO")] + [
            (t, "RELATED_TO") for t in self._ENTITY_REL_TABLES
            if t not in ("RELATED_TO", "CONTRADICTS")
        ]

        per_combo = max(1, limit // len(two_hop_combos))
        for r1_lbl, r2_lbl in two_hop_combos:
            try:
                if r1_lbl == "RELATED_TO":
                    query = (
                        f"MATCH (a:Entity)-[r1:RELATED_TO]->(b:Entity)"
                        f"-[r2:RELATED_TO]->(c:Entity)"
                        f" WHERE a.name = '{esc}'"
                        f" RETURN a.name, a.type, 'RELATED_TO', b.name, b.type,"
                        f"  'RELATED_TO', c.name, c.type,"
                        f"  COALESCE(r1.confidence, 0.8), COALESCE(r2.confidence, 0.8)"
                        f" LIMIT {per_combo}"
                    )
                else:
                    query = (
                        f"MATCH (a:Entity)-[r1:{r1_lbl}]->(b:Entity)"
                        f"-[r2:RELATED_TO]->(c:Entity)"
                        f" WHERE a.name = '{esc}'"
                        f" RETURN a.name, a.type, '{r1_lbl}', b.name, b.type,"
                        f"  'RELATED_TO', c.name, c.type,"
                        f"  COALESCE(r1.confidence, 0.8), COALESCE(r2.confidence, 0.8)"
                        f" LIMIT {per_combo}"
                    )

                result = self.conn.execute(query)
                while result.has_next():
                    row = result.get_next()
                    r1s = float(row[8]) if row[8] is not None else 0.8
                    r2s = float(row[9]) if row[9] is not None else 0.8
                    paths.append(RelationshipPath(
                        hop=2,
                        source_entity=row[0] or seed_entity,
                        source_type=row[1] or "UNKNOWN",
                        relation_type=row[2] or r1_lbl,
                        target_entity=row[3] or "",
                        target_type=row[4] or "UNKNOWN",
                        target_virtue=None,
                        second_relation=row[5] or r2_lbl,
                        third_entity=row[6],
                        strength=min(r1s, r2s),
                    ))
            except Exception as exc:  # noqa: BLE001
                logger.debug("2-hop[%s→%s] for %s: %s", r1_lbl, r2_lbl, seed_entity, exc)

        logger.debug("Found %d 2-hop paths for %s", len(paths), seed_entity)
        return paths[:limit]

    @staticmethod
    def _escape_cypher(text: str) -> str:
        """Escape special characters for Cypher string literals."""
        return text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def get_ontological_context(
    kuzu_conn: kuzu.Connection,
    seed_entity_name: str,
    entity_type: Optional[str] = None,
) -> str:
    """Extract ontological context as an LLM-ready premise string.

    Args:
        kuzu_conn:        Open KuzuDB connection.
        seed_entity_name: Entity to centre the extraction on.
        entity_type:      Optional Layer-1 type filter (e.g. "COUNTRY").

    Returns:
        Formatted string for prepending to an LLM prompt.
    """
    extractor = KuzuContextExtractor(kuzu_conn)
    context = extractor.extract_context(seed_entity_name, entity_type)
    return context.to_prompt_context()