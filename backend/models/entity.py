"""
Data models for three-layer ontological entity extraction.

Classes:
    EntityLabel        – single label with layer, value, description, and confidence
    OntologicalEntity  – fully-labelled entity with Layer 1 / 2 / 3 annotations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class EntityLabel:
    """Single ontological label for one layer."""

    layer: int          # 1, 2, or 3
    value: str          # The label text (e.g. "COUNTRY")
    description: str    # Human-readable meaning
    confidence: float   # 0.0–1.0


@dataclass
class OntologicalEntity:
    """Entity with three-layer ontological labelling."""

    name: str

    # ── Layer 1: Physical Type (exactly 1) ──────────────────────────────────
    physical_type: str              # e.g. "PERSON", "COUNTRY"
    physical_type_description: str  # Description of that type

    # ── Layer 2: Structural Role (1-2 roles) ────────────────────────────────
    structural_roles: List[str]                 # e.g. ["CATALYST", "AGGRESSOR"]
    role_descriptions: Dict[str, str]           # role → description mapping

    # ── Layer 3: Virtue / Vice (1-3 labels) ─────────────────────────────────
    philosophical_nature: List[str]             # e.g. ["DECEPTIVE", "RESILIENT"]
    virtue_descriptions: Dict[str, str]         # virtue → description mapping

    # ── Metadata ────────────────────────────────────────────────────────────
    confidence_score: float     # 0.0–1.0, average across all layer confidences
    source_text: str            # First 200 characters of the source text
    extracted_at: datetime      # Timestamp of extraction
    request_id: str             # ID of the analysis request

    # ── Optional enrichment ─────────────────────────────────────────────────
    narrative_context: Optional[str] = None
    relationships: List[Tuple[str, str]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict:
        """Convert to a JSON-serialisable dictionary."""
        return {
            "name": self.name,
            "layer1": {
                "value": self.physical_type,
                "description": self.physical_type_description,
            },
            "layer2": {
                "roles": self.structural_roles,
                "descriptions": self.role_descriptions,
            },
            "layer3": {
                "virtues": self.philosophical_nature,
                "descriptions": self.virtue_descriptions,
            },
            "confidence": self.confidence_score,
            "extracted_at": self.extracted_at.isoformat(),
            "context": self.narrative_context,
        }

    def to_graph_node(self) -> Dict:
        """Convert to a knowledge-graph node representation."""
        return {
            "id": self.name.lower().replace(" ", "_"),
            "name": self.name,
            "ontology_class": self.physical_type,
            "structural_roles": " | ".join(self.structural_roles),
            "virtues": " | ".join(self.philosophical_nature),
            "confidence": self.confidence_score,
            "properties": {
                "layer1": self.physical_type,
                "layer2": self.structural_roles,
                "layer3": self.philosophical_nature,
                "context": self.narrative_context,
            },
        }
