"""
Three-layer ontological entity extraction engine.

EntityExtractionEngine accepts raw news text and uses an LLM to produce
OntologicalEntity objects, each carrying:

  Layer 1 – Physical Type  (1 label)
  Layer 2 – Structural Role (1-2 labels)
  Layer 3 – Virtue / Vice  (1-3 labels)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
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
2. Return ONLY valid JSON array (no markdown, no explanation)
3. Focus on STRUCTURAL and PHILOSOPHICAL clarity, not sentiment
4. If unsure about a label, use closest semantic match
5. Do not return "UNKNOWN" – always make best assignment

## RESPONSE FORMAT (JSON ARRAY ONLY)
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
# Extraction engine
# ---------------------------------------------------------------------------

class EntityExtractionEngine:
    """Three-layer ontological entity extraction engine."""

    def __init__(self, llm_service: Any) -> None:
        self.llm = llm_service
        self.layer1_types = LAYER1_PHYSICAL_TYPES
        self.layer2_roles = LAYER2_STRUCTURAL_ROLES
        self.layer3_virtues = LAYER3_VIRTUE_VICE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        news_text: str,
        request_id: str,
    ) -> List[OntologicalEntity]:
        """Extract entities with three-layer labelling.

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

        raw_entities = self._parse_response(response)

        entities: List[OntologicalEntity] = []
        for raw in raw_entities:
            entity = self._create_ontological_entity(
                raw=raw,
                request_id=request_id,
                source_text=news_text,
            )
            if entity:
                entities.append(entity)

        return entities

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_response(self, response: str) -> List[Dict]:
        """Parse the LLM JSON response into a list of raw entity dicts."""
        if not response:
            return []
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Attempt to extract from markdown code blocks
        for delimiter in ("```json", "```"):
            if delimiter in response:
                parts = response.split(delimiter)
                if len(parts) >= 3:
                    try:
                        return json.loads(parts[1].strip())
                    except json.JSONDecodeError:
                        pass

        # Last resort: find the first JSON array in the text
        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass

        logger.warning("EntityExtractionEngine: could not parse LLM response")
        return []

    def _create_ontological_entity(
        self,
        raw: Dict,
        request_id: str,
        source_text: str,
    ) -> Optional[OntologicalEntity]:
        """Convert a raw LLM dict to a validated OntologicalEntity."""
        try:
            name = raw.get("name", "").strip()
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
                extracted_at=datetime.now(),
                request_id=request_id,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("EntityExtractionEngine: error creating entity from %r: %s", raw, exc)
            return None

    def _parse_multiple_labels(
        self,
        label_str: str,
        valid_labels: List[str],
    ) -> List[str]:
        """Parse underscore- or comma-separated labels, keeping only valid ones."""
        if not label_str:
            return []

        # Normalise: treat underscores as separators only when they appear between words
        # that are themselves valid labels; otherwise try comma split first.
        candidates_comma = [c.strip().upper() for c in label_str.split(",") if c.strip()]
        # If any element after comma-split is valid, prefer comma splitting
        if any(c in valid_labels for c in candidates_comma):
            candidates = candidates_comma
        else:
            # Fall back to underscore splitting
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
        layer1: str,  # noqa: ARG002 – reserved for future use
        layer2: List[str],
        layer3: List[str],
    ) -> float:
        """Confidence score based on label validation quality."""
        base = 0.85
        if "OBSERVER" in layer2:
            base -= 0.05
        if "PRAGMATIC" in layer3:
            base -= 0.05
        return round(max(0.5, min(1.0, base)), 4)
