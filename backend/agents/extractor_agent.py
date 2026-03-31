"""
ExtractorAgent v3 – Ontology-Constrained Triple Extraction
===========================================================

改进思路（参考 Agent-OM / ontology-llm）：

Agent-OM 核心设计：
  1. 不让 LLM 盲目提取实体——先把本体 Schema 作为 Context 注入 Prompt
  2. 三层信息检索：Syntactic（名称）→ Lexical（定义）→ Semantic（上下位关系）
  3. 提取后强制将实体映射到 ontology_subset.json 的合法节点类别

El-druin 对应改造：
  1. _generate_system_prompt：注入合法类型列表，LLM 必须映射，否则标记 UNKNOWN
  2. push_to_kuzu：所有节点统一写入 Entity 表（解决边=0 的根本修复）
  3. 三层信息丰富：给 LLM 更结构化的输入
  4. DB 路径统一：与 kuzu_graph.DEFAULT_DB_PATH 对齐
"""

import json
import logging
import os
import re
import sys
from typing import Any, Dict, List

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from dotenv import load_dotenv
from langchain_groq import ChatGroq  # type: ignore
from app.knowledge.graph_store import GraphStore

from app.core.config import Settings
_settings = Settings()
_KUZU_DB_PATH = _settings.kuzu_db_path

load_dotenv()
logger = logging.getLogger(__name__)


# ===========================================================================
# Ontology type normaliser（参考 Agent-OM ontology-as-context）
# ===========================================================================

class OntologyTypeNormaliser:
    """
    将 LLM 提取的 source_type/target_type 映射到 ontology_subset.json
    的合法类型集合。不合法则返回 "Entity"，不写入非法 typed label。
    """

    # 手工别名（syntactic layer）
    _MANUAL_ALIASES: Dict[str, str] = {
        "COUNTRY": "Location",   "NATION": "Location",
        "CITY": "Location",      "REGION": "Location",
        "PLACE": "Location",     "GEOGRAPHY": "Location",
        "COMPANY": "Organization","CORP": "Organization",
        "FIRM": "Organization",  "AGENCY": "Organization",
        "GOVERNMENT": "Organization","NGO": "Organization",
        "HUMAN": "Person",       "INDIVIDUAL": "Person",
        "POLITICIAN": "Person",  "LEADER": "Person",
        "INCIDENT": "Event",     "OCCURRENCE": "Event",
        "CONFLICT": "Event",     "CRISIS": "Event",
        "TECHNOLOGY": "Technology","TOOL": "Technology",
        "SOFTWARE": "Technology", "SYSTEM": "Technology",
        "GPE": "Location",       "ORG": "Organization",
        "SPORT": "Event",        "MATCH": "Event",
        "COMPANY_NAME": "Organization",
    }

    def __init__(self, ontology_path: str, relations_path: str) -> None:
        with open(ontology_path, encoding="utf-8") as f:
            self._ontology = json.load(f)
        with open(relations_path, encoding="utf-8") as f:
            self._relations = json.load(f)

        self._valid_types: Dict[str, str] = {
            k.upper(): k for k in self._ontology.get("classes", {}).keys()
        }
        self._edge_map: Dict[str, str] = {
            r["label"].upper().replace("-", "_"): r["label"]
            for r in self._relations.get("relations", [])
        }
        self._weight_map: Dict[str, float] = {
            r["label"]: r.get("logic_weight", 0.5)
            for r in self._relations.get("relations", [])
        }

    def normalise_type(self, raw_type: str) -> str:
        if not raw_type or raw_type.upper() == "UNKNOWN":
            return "UNKNOWN"
        upper = raw_type.strip().upper()
        if upper in self._valid_types:
            return self._valid_types[upper]
        if upper in self._MANUAL_ALIASES:
            alias_target = self._MANUAL_ALIASES[upper]
            if alias_target.upper() in self._valid_types:
                return self._valid_types[alias_target.upper()]
            return alias_target
        # 部分匹配
        for valid_upper, valid_canonical in self._valid_types.items():
            if valid_upper in upper or upper in valid_upper:
                return valid_canonical
        return "Entity"  # 兜底（非 UNKNOWN，允许写入）

    def normalise_edge(self, raw_edge: str) -> str:
        upper = raw_edge.strip().upper().replace("-", "_").replace(" ", "_")
        # 返回原始动词（作为 relation_type 属性值），若匹配则也保存规范名
        return self._edge_map.get(upper, raw_edge)

    def get_weight(self, edge_label: str) -> float:
        return self._weight_map.get(edge_label, 0.5)

    @property
    def valid_types(self) -> List[str]:
        return list(self._valid_types.values())

    @property
    def valid_edges(self) -> List[str]:
        return list(self._edge_map.values())

    def ontology_context_for_prompt(self) -> str:
        """注入 Prompt 的本体 Schema（对应 Agent-OM ontology-as-context）。"""
        return "\n".join([
            "【合法节点类型（source_type / target_type 必须从以下列表中选取）】",
            ", ".join(self.valid_types),
            "",
            "【合法关系类型（edge 尽量从以下列表选取；若无匹配，填写最接近的原文动词）】",
            ", ".join(self.valid_edges[:20]),
            "",
            "【约束】",
            "- 若实体类型无法映射到合法类型，填写 UNKNOWN（系统会丢弃该节点）。",
            "- source 和 target 必须来自原文，不得虚构。",
            "- 若文本中实体不足 2 个，返回 []。",
        ])


# ===========================================================================
# Text enricher（三层信息检索，参考 Agent-OM syntactic/lexical/semantic）
# ===========================================================================

class TextEnricher:
    """
    对新闻文本做三层结构化预处理。
    Syntactic → 实体候选名称
    Lexical   → 关系动词候选
    Semantic  → 句法层面的主谓宾提示
    """

    _KNOWN_ABBREVS = {
        "UN","NATO","WHO","IMF","WTO","EU","FBI","CIA",
        "Fed","ECB","OPEC","G7","G20","IAEA","ICC","US","UK","USA",
    }
    _VERB_RE = re.compile(
        r"\b(attack(?:ed|s)?|sanction(?:ed|s)?|invad(?:ed|es?)|sign(?:ed|s)?|"
        r"agree(?:d|s)?|support(?:ed|s)?|oppos(?:ed|es?)|condemn(?:ed|s)?|"
        r"meet(?:s|ing)?|met|acquir(?:ed|es?)|launch(?:ed|es?)|clos(?:ed|es?)|"
        r"ban(?:ned|s)?|withdraw(?:s|n)?|withdrew|expel(?:led|s)?|"
        r"impos(?:ed|es?)|refus(?:ed|es?)|deploy(?:ed|s)?|accus(?:ed|es?)|"
        r"negotiat(?:ed|es?)|scores?|wins?|beat|defeated|plays?|joins?|leads?)\b",
        re.IGNORECASE,
    )

    def enrich(self, text: str) -> Dict[str, Any]:
        syn = self._syntactic(text)
        lex = self._lexical(text)
        sem = self._semantic(text, syn, lex)
        return {"syntactic_entities": syn, "lexical_relations": lex, "semantic_hints": sem}

    def _syntactic(self, text: str) -> List[str]:
        entities, seen = [], set()
        for ab in self._KNOWN_ABBREVS:
            if re.search(r"\b" + re.escape(ab) + r"\b", text) and ab not in seen:
                seen.add(ab); entities.append(ab)
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text):
            n = m.group(1)
            if n not in seen and len(n) > 3:
                seen.add(n); entities.append(n)
        return entities[:12]

    def _lexical(self, text: str) -> List[str]:
        verbs, seen = [], set()
        for m in self._VERB_RE.finditer(text):
            v = m.group(1).lower()
            if v not in seen:
                seen.add(v); verbs.append(v)
        return verbs[:6]

    def _semantic(self, text: str, entities: List[str], relations: List[str]) -> List[str]:
        hints = []
        for rel in relations:
            for m in re.finditer(
                r"([A-Z][a-z\s]{2,25})\s+" + re.escape(rel) + r"\s+([A-Z][a-z\s]{2,25})",
                text, re.IGNORECASE,
            ):
                s, o = m.group(1).strip(), m.group(2).strip()
                if s and o and s != o:
                    hints.append(f"{s} --[{rel}]--> {o}")
        return hints[:5]


# ===========================================================================
# ExtractorAgent v3
# ===========================================================================

class ExtractorAgent:

    def __init__(self) -> None:
        self.llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.0)

        # Align DB path
        try:
            from app.core.config import get_settings
            s = get_settings()
            if getattr(s, "kuzu_db_path", None) != _KUZU_DB_PATH:
                logger.warning("Overriding kuzu_db_path → %s", _KUZU_DB_PATH)
                s.kuzu_db_path = _KUZU_DB_PATH
        except Exception as exc:
            logger.warning("Could not patch kuzu_db_path: %s", exc)

        self.store = GraphStore(backend="kuzu")
        logger.info("ExtractorAgent v3: DB at %s", _KUZU_DB_PATH)

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        CFG_DIR  = os.path.join(BASE_DIR, "config")
        self.normaliser = OntologyTypeNormaliser(
            ontology_path=os.path.join(CFG_DIR, "ontology_subset.json"),
            relations_path=os.path.join(CFG_DIR, "relations.json"),
        )
        self.enricher = TextEnricher()

    # ------------------------------------------------------------------
    # Prompt（本体约束注入）
    # ------------------------------------------------------------------

    def _system_prompt(self) -> str:
        return (
            "你是专业知识图谱三元组提取专家。从新闻文本中提取实体关系，"
            "并严格映射到给定本体 Schema。\n\n"
            + self.normaliser.ontology_context_for_prompt()
            + "\n\n【输出格式】JSON 数组，每个元素包含：\n"
            '  "source", "source_type", "target", "target_type", "edge", "confidence", "desc"\n'
            "只返回 JSON 数组，不加任何说明。"
        )

    def _user_prompt(self, text: str, enriched: Dict[str, Any]) -> str:
        syn = ", ".join(enriched["syntactic_entities"]) or "（未检测到）"
        lex = ", ".join(enriched["lexical_relations"])  or "（未检测到）"
        sem = "\n  ".join(enriched["semantic_hints"])   or "（未检测到）"
        return (
            f"【原始新闻文本】\n{text}\n\n"
            f"【预提取辅助信息（以原文为准）】\n"
            f"Syntactic（实体候选）: {syn}\n"
            f"Lexical（关系动词候选）: {lex}\n"
            f"Semantic（句法提示）:\n  {sem}\n\n"
            "请根据以上信息提取三元组并按格式返回 JSON 数组。"
        )

    # ------------------------------------------------------------------
    # Write to KuzuDB（统一 Entity 表 — 解决边=0 的根本修复）
    # ------------------------------------------------------------------

    def push_to_kuzu(self, triplets: List[Dict[str, Any]]) -> int:
        """
        修复核心：所有节点统一写入 Entity 表。
        RELATED_TO FROM Entity TO Entity 约束永远满足。
        具体动词保存在 relation_type 属性中。
        """
        print(f"\n--- GraphStore 同步开始 (共 {len(triplets)} 条) ---")
        success = 0

        for tri in triplets:
            try:
                s_name = (tri.get("source") or "").strip()
                t_name = (tri.get("target") or "").strip()
                if not s_name or not t_name or s_name == t_name:
                    continue

                # 本体类型映射
                s_type = self.normaliser.normalise_type(str(tri.get("source_type", "")))
                t_type = self.normaliser.normalise_type(str(tri.get("target_type", "")))

                # 丢弃 UNKNOWN
                if s_type == "UNKNOWN" or t_type == "UNKNOWN":
                    print(f"⚠️ [跳过UNKNOWN] {s_name}({tri.get('source_type')}) → {t_name}({tri.get('target_type')})")
                    continue

                raw_edge = str(tri.get("edge", "RELATED_TO"))
                edge     = self.normaliser.normalise_edge(raw_edge)
                weight   = float(tri.get("confidence", self.normaliser.get_weight(edge)))

                # 先确保端点节点存在于 Entity 表
                self.store.add_entity(s_name, s_type)
                self.store.add_entity(t_name, t_type)

                # 写关系（RELATED_TO，relation_type 属性保存原始动词）
                self.store.add_relation(
                    from_name=s_name, from_type=s_type,
                    to_name=t_name,   to_type=t_type,
                    relation_type=edge,
                    weight=weight,
                )
                print(f"✅ {s_name}({s_type}) --[{edge}]--> {t_name}({t_type})  conf={weight:.2f}")
                success += 1

            except Exception as exc:
                print(f"❌ [异常]: {exc}")
                logger.error("push_to_kuzu: %s | triple=%s", exc, tri)

        # 诊断
        try:
            rels = self.store.get_relations(limit=5000)
            ents = self.store.get_entities(limit=5000)
            print(f"\n--- 写入后诊断 ---\n  Entities: {len(ents)}\n  Edges: {len(rels)}\n  本次写入: {success}/{len(triplets)}")
        except Exception as exc:
            logger.warning("Diagnostic failed: %s", exc)

        return success

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def extract_and_sync(self, text: str) -> None:
        print("🤖 三层信息提取 + 本体约束 LLM 提取...")
        enriched = self.enricher.enrich(text)

        res = self.llm.invoke([
            ("system", self._system_prompt()),
            ("human",  self._user_prompt(text, enriched)),
        ])

        match = re.search(r"\[.*\]", res.content, re.DOTALL)
        if not match:
            print(f"❌ LLM 未返回有效 JSON。\n{res.content[:500]}")
            return

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as exc:
            print(f"❌ JSON 解析失败: {exc}")
            return

        print("\n--- LLM 提取结果 ---")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if data:
            self.push_to_kuzu(data)
        else:
            print("⚠️ LLM 返回空数组。")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = ExtractorAgent()
    agent.extract_and_sync(
        "Spain closed its airspace to US military planes involved in war on Iran, "
        "as Madrid refused to let Washington use jointly operated bases."
    )