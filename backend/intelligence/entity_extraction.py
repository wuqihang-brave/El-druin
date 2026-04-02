"""
Three-layer ontological entity extraction engine.

EntityExtractionEngine accepts raw news text and uses an LLM to produce
OntologicalEntity objects, each carrying:

  Layer 1 – Physical Type  (1 label)
  Layer 2 – Structural Role (1-2 labels)
  Layer 3 – Virtue / Vice  (1-3 labels)

修复说明 (v2):
  Bug: `Skipping unknown type: 'entities'`
  根因：LLM 有时返回包裹对象而非裸数组：
    {"entities": [...], "relations": [...]}  ← 包裹对象
    [...]                                     ← 裸数组（期望格式）
  原版 _parse_response 只处理裸数组，遇到包裹对象时返回整个 dict。
  extract() 对这个 dict 做 `for raw in raw_entities`，
  Python 迭代 dict 会得到 key 字符串 ("entities", "relations")，
  导致 handle_raw_entity("entities") 落入 else 分支并打印 Skipping。

  修复：_parse_response 改为 _extract_entity_list()，能识别：
    1. 裸数组 [...]
    2. 包裹对象 {"entities": [...]}
    3. 嵌套包裹 {"data": {"entities": [...]}}
    4. markdown 代码块
    5. 最后兜底：正则找第一个 [...] 片段
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.entity import OntologicalEntity
from intelligence.entity_labels import (
    LAYER1_PHYSICAL_TYPES,
    LAYER2_STRUCTURAL_ROLES,
    LAYER3_VIRTUE_VICE,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM system prompt
# ---------------------------------------------------------------------------

ENTITY_EXTRACTION_SYSTEM_PROMPT = """\
You are an Ontological Intelligence Officer specialising in multi-dimensional entity analysis.

Your task: Extract ALL key entities from news text and assign THREE layers of labels.

## LAYER 1: Physical Type
Identify WHAT the entity is structurally.
Options: PERSON, ORGANIZATION, COUNTRY, CITY, CORPORATION, REGULATORY_BODY, ALLIANCE, \
EVENT, TECHNOLOGY, IDEOLOGY, RESOURCE, CURRENCY, CONFLICT, MEDIA

Choose the single most accurate type. Do not combine.

## LAYER 2: Structural Role
Identify HOW the entity functions in this narrative.
Options: AGGRESSOR, DEFENDER, PIVOT, FRAGILE_STATE, CATALYST, REGULATOR, ENABLER, VICTIM, \
BENEFICIARY, OBSERVER, INTERMEDIARY, VICTIM_TURNED_AGGRESSOR, DEUS_EX_MACHINA, CONSTRAINT, \
OPPORTUNITY, HEDGE, AMPLIFIER

You may assign 1-2 roles if they both apply. Separate multiple roles with underscore: ROLE1_ROLE2

## LAYER 3: Virtue/Vice (Bamboo/Plum Philosophy)
Identify the PHILOSOPHICAL NATURE of the entity.

Bamboo (Flexible): RESILIENT, ADAPTIVE, PRAGMATIC, NEGOTIABLE, RESPONSIVE, EMBEDDED
Plum (Unbending):  PRINCIPLED, RIGID, IDEOLOGICAL, DEFIANT, ISOLATED, UNWAVERING
Deception:         DECEPTIVE, OPAQUE, DUPLICITOUS, MASKED, CALCULATED, MANIPULATIVE
Emergent:          RISING_POWER, DECLINING_POWER, TRANSFORMING, CHAOTIC, PARADOXICAL, \
VOLATILE, STABILIZING

You may assign 1-3 labels. Separate multiple labels with underscore: VIRTUE1_VIRTUE2

## RULES
1. Every entity gets exactly 1 Layer 1, 1-2 Layer 2, and 1-3 Layer 3 labels
2. Return ONLY a valid JSON array — NO wrapper object, NO markdown, NO explanation
3. The response MUST start with [ and end with ]
4. Focus on STRUCTURAL and PHILOSOPHICAL clarity, not sentiment
5. If unsure about a label, use closest semantic match
6. Do not return "UNKNOWN" – always make best assignment

## RESPONSE FORMAT (JSON ARRAY ONLY — must be a bare array, not wrapped in an object)
[
  {
    "name": "Entity Name Here",
    "layer1": "PHYSICAL_TYPE",
    "layer2": "ROLE_OR_ROLE1_ROLE2",
    "layer3": "VIRTUE_OR_VIRTUE1_VIRTUE2_VIRTUE3"
  }
]

Extract entities from the following text:\
"""


# ---------------------------------------------------------------------------
# Robust JSON / entity-list parser
# ---------------------------------------------------------------------------

def _extract_entity_list(response: Any) -> List[Dict]:
    """
    Robustly extract a list of entity dicts from an LLM response.

    Handles all observed LLM output shapes:
      1. Already a Python list   → return directly
      2. Already a Python dict   → look for "entities" / "data" key
      3. JSON string – bare array   [...] → parse
      4. JSON string – wrapped object {"entities": [...]} → unwrap
      5. Markdown code block    ```json [...] ``` → strip, parse
      6. Last resort             → regex-find first [...] fragment

    This fixes the `Skipping unknown type: 'entities'` error that occurs
    when the LLM returns a dict and the caller iterates over its keys.
    """
    if not response:
        return []

    # ── Case 1: already a Python list ────────────────────────────────────
    if isinstance(response, list):
        return response

    # ── Case 2: already a Python dict ────────────────────────────────────
    if isinstance(response, dict):
        return _unwrap_dict(response)

    # ── String handling ──────────────────────────────────────────────────
    text = str(response).strip()

    # Strip markdown code fences
    text = re.sub(r"^```[a-zA-Z0-9]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text.rstrip())
    text = text.strip()

    # Try direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return _unwrap_dict(parsed)
    except json.JSONDecodeError:
        pass

    # Last resort: find the first complete [...] substring
    start = text.find("[")
    end   = text.rfind("]") + 1
    if 0 <= start < end:
        try:
            parsed = json.loads(text[start:end])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.warning("EntityExtractionEngine: could not extract entity list from response")
    return []


def _unwrap_dict(d: Dict) -> List[Dict]:
    """
    Unwrap an LLM response dict to find the entity list.

    Common patterns:
      {"entities": [...]}
      {"data": {"entities": [...]}}
      {"result": [...]}
    """
    # Direct "entities" key (most common LLM misbehaviour)
    if "entities" in d and isinstance(d["entities"], list):
        return d["entities"]
    # Other common wrappers
    for key in ("data", "result", "items", "output"):
        val = d.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, dict) and "entities" in val:
            return val["entities"]  # type: ignore[return-value]
    # If the dict values contain a list, return the first one found
    for val in d.values():
        if isinstance(val, list):
            return val  # type: ignore[return-value]
    logger.warning("EntityExtractionEngine: dict response has no entity list: keys=%s", list(d.keys()))
    return []


# ---------------------------------------------------------------------------
# Extraction engine
# ---------------------------------------------------------------------------

class EntityExtractionEngine:
    """Three-layer ontological entity extraction engine."""

    def __init__(self, llm_service: Any) -> None:
        self.llm = llm_service
        self.layer1_types  = LAYER1_PHYSICAL_TYPES
        self.layer2_roles  = LAYER2_STRUCTURAL_ROLES
        self.layer3_virtues = LAYER3_VIRTUE_VICE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        news_text: str,
        request_id: str,
    ) -> List[OntologicalEntity]:
        """
        Extract entities with three-layer labelling.

        Args:
            news_text:  Raw news article text.
            request_id: Identifier of the parent analysis request.

        Returns:
            List of validated OntologicalEntity objects.
        """
        prompt = ENTITY_EXTRACTION_SYSTEM_PROMPT + f"\n\n{news_text}"

        response = self.llm.call(
            prompt=prompt,
            temperature=0.2,
            max_tokens=2000,
            response_format="json",
        )

        # ── v2 fix: use robust parser that handles dict-wrapped responses ──
        raw_entities = _extract_entity_list(response)

        entities: List[OntologicalEntity] = []

        def handle_raw_entity(raw_item: Any) -> None:
            if isinstance(raw_item, dict):
                entity = self._create_ontological_entity(
                    raw=raw_item,
                    request_id=request_id,
                    source_text=news_text,
                )
                if entity:
                    entities.append(entity)
            elif isinstance(raw_item, list):
                for sub in raw_item:
                    handle_raw_entity(sub)
            else:
                # String/int/None — skip silently at DEBUG level
                logger.debug(
                    "EntityExtractionEngine: skipping non-dict item type=%s value=%r",
                    type(raw_item).__name__, raw_item,
                )

        for raw in raw_entities:
            handle_raw_entity(raw)

        logger.info(
            "EntityExtractionEngine: extracted %d entities (request_id=%s)",
            len(entities), request_id,
        )
        return entities

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_ontological_entity(
        self,
        raw: Dict,
        request_id: str,
        source_text: str,
    ) -> Optional[OntologicalEntity]:
        """Convert a raw LLM dict to a validated OntologicalEntity."""
        try:
            name   = raw.get("name", "").strip()
            layer1 = raw.get("layer1", "").strip().upper()
            layer2 = raw.get("layer2", "").strip().upper()
            layer3 = raw.get("layer3", "").strip().upper()

            if not name or not layer1:
                return None

            # Validate / fuzzy-match Layer 1
            if layer1 not in self.layer1_types:
                layer1 = self._fuzzy_match_label(layer1, list(self.layer1_types.keys()))
                if not layer1:
                    return None

            # Parse Layer 2 (1-2 roles)
            roles = self._parse_multiple_labels(layer2, list(self.layer2_roles.keys()))
            if not roles:
                roles = ["OBSERVER"]

            # Parse Layer 3 (1-3 virtues/vices)
            virtues = self._parse_multiple_labels(layer3, list(self.layer3_virtues.keys()))
            if not virtues:
                virtues = ["PRAGMATIC"]

            confidence = self._calculate_confidence(layer1, roles, virtues)

            return OntologicalEntity(
                name=name,
                physical_type=layer1,
                physical_type_description=self.layer1_types[layer1],
                structural_roles=roles,
                role_descriptions={role: self.layer2_roles[role] for role in roles},
                philosophical_nature=virtues,
                virtue_descriptions={v: self.layer3_virtues[v] for v in virtues},
                confidence_score=confidence,
                source_text=source_text[:200],
                extracted_at=datetime.now(timezone.utc),
                request_id=request_id,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "EntityExtractionEngine: error creating entity from %r: %s", raw, exc
            )
            return None

    def _parse_multiple_labels(
        self,
        label_str: str,
        valid_labels: List[str],
    ) -> List[str]:
        """Parse underscore- or comma-separated labels, keeping only valid ones."""
        if not label_str:
            return []

        candidates_comma = [c.strip().upper() for c in label_str.split(",") if c.strip()]
        if any(c in valid_labels for c in candidates_comma):
            candidates = candidates_comma
        else:
            candidates = [c.strip().upper() for c in label_str.split("_") if c.strip()]

        valid = [c for c in candidates if c in valid_labels]
        return valid[:3]

    def _fuzzy_match_label(
        self,
        label: str,
        valid_labels: List[str],
    ) -> Optional[str]:
        """Return the first valid label that contains *label* as a substring (or vice-versa)."""
        for valid in valid_labels:
            if label in valid or valid in label:
                return valid
        return None

    def _calculate_confidence(
        self,
        layer1: str,
        layer2: List[str],
        layer3: List[str],
    ) -> float:
        base = 0.85
        if "OBSERVER" in layer2:
            base -= 0.05
        if "PRAGMATIC" in layer3:
            base -= 0.05
        return round(max(0.5, min(1.0, base)), 4)