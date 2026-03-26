"""
Schema.org + PROV-O Ontology Configuration for El-druin Knowledge Graph.

Defines the canonical entity types (based on Schema.org) and relationship types
(following PROV-O standards) that constrain the knowledge graph extraction
pipeline.  Validation helpers and an LLM system-prompt generator are included
so that downstream components can enforce ontological compliance at runtime.

References:
    - Schema.org: https://schema.org
    - PROV-O (W3C): https://www.w3.org/TR/prov-o/
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Optional, Tuple

# ---------------------------------------------------------------------------
# CORE ONTOLOGY
# ---------------------------------------------------------------------------

CORE_ONTOLOGY: Dict[str, Dict] = {
    # ── NODE TYPES (Schema.org) ───────────────────────────────────────────
    "NODES": {
        "NewsArticle": {
            "description": "A news article or journalistic report.",
            "schema_url": "https://schema.org/NewsArticle",
            "examples": ["Reuters report on sanctions", "Bloomberg AI funding article"],
        },
        "Person": {
            "description": "A human being, including public figures, officials, and executives.",
            "schema_url": "https://schema.org/Person",
            "examples": ["Joe Biden", "Xi Jinping", "Elon Musk"],
        },
        "Organization": {
            "description": (
                "A structured group with a collective goal: companies, governments,"
                " NGOs, military alliances, regulatory bodies."
            ),
            "schema_url": "https://schema.org/Organization",
            "examples": ["NATO", "OpenAI", "UN Security Council", "Federal Reserve"],
        },
        "Place": {
            "description": (
                "A geographic location, region, country, city, or strategic area."
            ),
            "schema_url": "https://schema.org/Place",
            "examples": ["United States", "Strait of Hormuz", "Silicon Valley"],
        },
        "Event": {
            "description": "A discrete occurrence in time: conflict, summit, election, crisis.",
            "schema_url": "https://schema.org/Event",
            "examples": ["Russia-Ukraine War", "G20 Summit", "Gaza Conflict 2023"],
        },
        "CreativeWork": {
            "description": "A creative or intellectual work: book, policy paper, treaty, report.",
            "schema_url": "https://schema.org/CreativeWork",
            "examples": ["Paris Agreement", "CHIPS Act", "IPCC Report"],
        },
        "SoftwareApplication": {
            "description": "A software system, AI model, platform, or digital application.",
            "schema_url": "https://schema.org/SoftwareApplication",
            "examples": ["GPT-4", "Llama 3", "SWIFT banking system"],
        },
        "Dataset": {
            "description": "A structured collection of data used for analysis or training.",
            "schema_url": "https://schema.org/Dataset",
            "examples": ["ImageNet", "Common Crawl", "IMF GDP dataset"],
        },
        "Technique": {
            "description": "A technical method, algorithm, or approach.",
            "schema_url": "https://schema.org/Technique",
            "examples": ["Transformer architecture", "RLHF", "Zero-day exploit"],
        },
        "Indicator": {
            "description": "A generic metric or observable measurement.",
            "schema_url": "https://schema.org/Observation",
            "examples": ["GDP growth rate", "unemployment rate", "inflation index"],
        },
        "ThreatIndicator": {
            "description": (
                "A security threat indicator: malware signature, vulnerability,"
                " attack pattern (cf. PROV-O prov:Entity with threat context)."
            ),
            "schema_url": "https://schema.org/Observation",
            "examples": ["CVE-2024-0001", "APT29 TTPs", "ransomware campaign"],
        },
        "EconomicIndicator": {
            "description": "An economic metric signalling market or macro-economic conditions.",
            "schema_url": "https://schema.org/Observation",
            "examples": ["CPI", "Federal Funds Rate", "trade deficit"],
        },
        "GeopoliticalIndicator": {
            "description": "A geopolitical risk or stability indicator.",
            "schema_url": "https://schema.org/Observation",
            "examples": [
                "nuclear threat level", "sanctions effectiveness index",
                "military readiness score",
            ],
        },
    },

    # ── EDGE TYPES (PROV-O) ───────────────────────────────────────────────
    "EDGES": {
        # Actor-to-Actor relations
        "works_for": {
            "description": "A Person works for an Organization.",
            "prov": "prov:wasAssociatedWith",
            "examples": ["Jerome Powell works_for Federal Reserve"],
        },
        "leads": {
            "description": "A Person leads / directs an Organization.",
            "prov": "prov:wasAssociatedWith",
            "examples": ["Sam Altman leads OpenAI"],
        },
        "member_of": {
            "description": "An entity is a member of a group or alliance.",
            "prov": "prov:wasAssociatedWith",
            "examples": ["Turkey member_of NATO"],
        },
        "allied_with": {
            "description": "Cooperative or strategic alliance between entities.",
            "prov": "prov:wasAssociatedWith",
            "examples": ["Russia allied_with China"],
        },
        "antagonistic_to": {
            "description": "Hostile, adversarial, or sanctions-based relationship.",
            "prov": "prov:wasInfluencedBy",
            "examples": ["US antagonistic_to Iran", "Israel antagonistic_to Hezbollah"],
        },
        "competes_with": {
            "description": "Competitive relationship in market or geopolitical sphere.",
            "prov": "prov:wasInfluencedBy",
            "examples": ["US competes_with China (AI dominance)"],
        },

        # Geographic relations
        "located_in": {
            "description": "An entity is physically located in a Place.",
            "prov": "prov:wasAssociatedWith",
            "examples": ["OpenAI located_in San Francisco"],
        },
        "operates_in": {
            "description": "An entity actively operates within a Place.",
            "prov": "prov:wasAssociatedWith",
            "examples": ["Hezbollah operates_in Lebanon"],
        },
        "originates_from": {
            "description": "An entity or concept originates from a Place.",
            "prov": "prov:hadPrimarySource",
            "examples": ["Oil originates_from Saudi Arabia"],
        },

        # Media / content relations
        "mentions": {
            "description": "A NewsArticle or CreativeWork mentions an entity.",
            "prov": "prov:used",
            "examples": ["Reuters_article mentions Federal Reserve"],
        },
        "reports_on": {
            "description": "A NewsArticle reports on an Event or entity.",
            "prov": "prov:used",
            "examples": ["BBC_News reports_on Gaza_Conflict"],
        },
        "cites": {
            "description": "An article or work cites another work as a source.",
            "prov": "prov:wasDerivedFrom",
            "examples": ["IPCC_2023 cites IPCC_2021"],
        },

        # Causal / event relations
        "involved_in": {
            "description": "An entity is involved in an Event.",
            "prov": "prov:wasAssociatedWith",
            "examples": ["Russia involved_in Ukraine_War"],
        },
        "caused_by": {
            "description": "An event or state was caused by another entity or event.",
            "prov": "prov:wasDerivedFrom",
            "examples": ["inflation caused_by supply_chain_disruption"],
        },
        "impacts": {
            "description": "An entity impacts / influences another entity or indicator.",
            "prov": "prov:wasInfluencedBy",
            "examples": ["sanctions impacts trade_volume"],
        },

        # Technology relations
        "implements": {
            "description": "A SoftwareApplication implements a Technique.",
            "prov": "prov:used",
            "examples": ["GPT-4 implements Transformer_architecture"],
        },
        "vulnerable_to": {
            "description": "A system or entity is vulnerable to a ThreatIndicator.",
            "prov": "prov:wasInfluencedBy",
            "examples": ["SWIFT_system vulnerable_to cyberattack"],
        },
        "infected_by": {
            "description": "A system or entity has been infected by a threat.",
            "prov": "prov:wasInfluencedBy",
            "examples": ["hospital_network infected_by ransomware"],
        },
        "targets": {
            "description": "A threat or adversary targets a system or entity.",
            "prov": "prov:used",
            "examples": ["APT29 targets US_government"],
        },
        "depends_on": {
            "description": "An entity functionally depends on another.",
            "prov": "prov:wasDerivedFrom",
            "examples": ["AI_training depends_on GPU_supply"],
        },
        "provides": {
            "description": "An entity provides a service, resource, or capability.",
            "prov": "prov:generated",
            "examples": ["OPEC provides oil_supply"],
        },
        "uses": {
            "description": "An entity uses a resource, tool, or service.",
            "prov": "prov:used",
            "examples": ["Data_Center uses Renewable_Energy"],
        },

        # Indicator relations
        "signals": {
            "description": "An Indicator signals a state, trend, or condition.",
            "prov": "prov:generated",
            "examples": ["CPI signals inflation_trend"],
        },

        # PROV-O provenance relations
        "attributed_to": {
            "description": (
                "Information or an entity is attributed to a source"
                " (PROV-O prov:wasAttributedTo)."
            ),
            "prov": "prov:wasAttributedTo",
            "examples": ["intelligence_report attributed_to CIA"],
        },
        "verified_by": {
            "description": "A claim or entity has been verified by an authority.",
            "prov": "prov:wasAttributedTo",
            "examples": ["nuclear_activity verified_by IAEA"],
        },
        "contradicts": {
            "description": "An entity or claim contradicts another.",
            "prov": "prov:wasInfluencedBy",
            "examples": ["Russia_statement contradicts UN_resolution"],
        },
    },
}

# ---------------------------------------------------------------------------
# Convenience sets for fast O(1) membership testing
# ---------------------------------------------------------------------------

VALID_NODE_TYPES: FrozenSet[str] = frozenset(CORE_ONTOLOGY["NODES"].keys())
VALID_EDGE_TYPES: FrozenSet[str] = frozenset(CORE_ONTOLOGY["EDGES"].keys())

# ---------------------------------------------------------------------------
# Legacy type mapping
# Maps raw LLM-output type strings → canonical Schema.org node types.
# ---------------------------------------------------------------------------

LEGACY_NODE_MAP: Dict[str, str] = {
    # Geographic / political entities
    "GPE": "Place",
    "LOC": "Place",
    "LOCATION": "Place",
    "COUNTRY": "Place",
    "CITY": "Place",
    "REGION": "Place",
    "TERRITORY": "Place",
    # Organisations
    "ORG": "Organization",
    "ORGANIZATION": "Organization",
    "COMPANY": "Organization",
    "INSTITUTION": "Organization",
    "GOVERNMENT": "Organization",
    "ALLIANCE": "Organization",
    "MILITARY": "Organization",
    "NGO": "Organization",
    # Persons
    "PERSON": "Person",
    "PER": "Person",
    "INDIVIDUAL": "Person",
    "LEADER": "Person",
    # Events
    "EVENT": "Event",
    "CONFLICT": "Event",
    "CRISIS": "Event",
    "SUMMIT": "Event",
    # Software / AI
    "PRODUCT": "SoftwareApplication",
    "SOFTWARE": "SoftwareApplication",
    "AI_MODEL": "SoftwareApplication",
    "AI": "SoftwareApplication",
    "PLATFORM": "SoftwareApplication",
    # Data
    "DATA": "Dataset",
    "DATASET": "Dataset",
    # Articles / content
    "ARTICLE": "NewsArticle",
    "NEWS": "NewsArticle",
    "REPORT": "CreativeWork",
    "POLICY": "CreativeWork",
    "TREATY": "CreativeWork",
    # Techniques
    "METHOD": "Technique",
    "ALGORITHM": "Technique",
    "TECHNIQUE": "Technique",
    "TECHNOLOGY": "Technique",
    # Indicators
    "INDICATOR": "Indicator",
    "THREAT": "ThreatIndicator",
    "VULNERABILITY": "ThreatIndicator",
    "ECONOMIC": "EconomicIndicator",
    "GEOPOLITICAL": "GeopoliticalIndicator",
    # Fallback
    "MISC": "Indicator",
    "OTHER": "Indicator",
}

# ---------------------------------------------------------------------------
# Legacy relation mapping
# Maps raw LLM-output relation strings → canonical PROV-O edge types.
# ---------------------------------------------------------------------------

LEGACY_EDGE_MAP: Dict[str, str] = {
    # Antagonistic
    "sanctions":       "antagonistic_to",
    "sanctioned":      "antagonistic_to",
    "invades":         "antagonistic_to",
    "invaded":         "antagonistic_to",
    "attacks":         "antagonistic_to",
    "attacked":        "antagonistic_to",
    "opposes":         "antagonistic_to",
    "condemned":       "antagonistic_to",
    "condemns":        "antagonistic_to",
    "strikes":         "antagonistic_to",
    "military_strike": "antagonistic_to",
    "strategic_rival": "antagonistic_to",
    "blockades":       "antagonistic_to",
    "threatens":       "antagonistic_to",
    # Allied / cooperative
    "alliance":        "allied_with",
    "allied":          "allied_with",
    "supports":        "allied_with",
    "partners_with":   "allied_with",
    "cooperates_with": "allied_with",
    "signs":           "allied_with",
    "meets":           "allied_with",
    "agrees_with":     "allied_with",
    # Impact / causal
    "controls":        "impacts",
    "democratizes":    "impacts",
    "flows_through":   "impacts",
    "regulates":       "impacts",
    "enables":         "impacts",
    "raises":          "impacts",
    "cuts":            "impacts",
    "launches":        "impacts",
    "disputes":        "impacts",
    "conflict":        "impacts",
    # Causal (caused_by direction)
    "causes":          "caused_by",
    # Dependency
    "raises_funding_from": "depends_on",
    "consumes":        "depends_on",
    "acquires":        "depends_on",
    "hub_of":          "provides",
    "related_to":      "impacts",
    # Geographic
    "located_in":      "located_in",
    "operates_in":     "operates_in",
    "originates_from": "originates_from",
    # Content
    "mentions":        "mentions",
    "reports_on":      "reports_on",
    "cites":           "cites",
    # Technology
    "implements":      "implements",
    "vulnerable_to":   "vulnerable_to",
    "infected_by":     "infected_by",
    "targets":         "targets",
    "depends_on":      "depends_on",
    "provides":        "provides",
    "uses":            "uses",
    # Identity
    "works_for":       "works_for",
    "leads":           "leads",
    "member_of":       "member_of",
    "involved_in":     "involved_in",
    # Provenance
    "attributed_to":   "attributed_to",
    "verified_by":     "verified_by",
    "contradicts":     "contradicts",
    # Indicators
    "signals":         "signals",
}


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_node_type(raw_type: str) -> Optional[str]:
    """Map a raw LLM-output node type to the canonical Schema.org type.

    Resolution order:
    1. Already a valid canonical type → return as-is.
    2. Found in LEGACY_NODE_MAP → return mapped type.
    3. Case-insensitive match in VALID_NODE_TYPES → return normalised.
    4. Case-insensitive match in LEGACY_NODE_MAP → return mapped type.
    5. None → caller should decide on fallback.

    Args:
        raw_type: The raw node type string produced by the LLM.

    Returns:
        Canonical Schema.org type string, or ``None`` if unmappable.
    """
    if not raw_type:
        return None

    # Exact match (canonical)
    if raw_type in VALID_NODE_TYPES:
        return raw_type

    # Exact match (legacy)
    if raw_type in LEGACY_NODE_MAP:
        return LEGACY_NODE_MAP[raw_type]

    # Case-insensitive canonical match
    upper = raw_type.upper()
    for canonical in VALID_NODE_TYPES:
        if canonical.upper() == upper:
            return canonical

    # Case-insensitive legacy match
    for legacy, canonical in LEGACY_NODE_MAP.items():
        if legacy.upper() == upper:
            return canonical

    return None


def validate_edge_type(raw_relation: str) -> Optional[str]:
    """Map a raw LLM-output relation string to the canonical PROV-O edge type.

    Resolution order:
    1. Already a valid canonical edge type → return as-is.
    2. Found in LEGACY_EDGE_MAP → return mapped type.
    3. Case-insensitive canonical match → return normalised.
    4. Case-insensitive legacy match → return mapped type.
    5. None → caller should decide on fallback.

    Args:
        raw_relation: The raw relation/predicate string produced by the LLM.

    Returns:
        Canonical PROV-O edge type string, or ``None`` if unmappable.
    """
    if not raw_relation:
        return None

    # Exact match (canonical)
    if raw_relation in VALID_EDGE_TYPES:
        return raw_relation

    # Exact match (legacy)
    if raw_relation in LEGACY_EDGE_MAP:
        return LEGACY_EDGE_MAP[raw_relation]

    # Case-insensitive canonical match
    lower = raw_relation.lower()
    for canonical in VALID_EDGE_TYPES:
        if canonical.lower() == lower:
            return canonical

    # Case-insensitive legacy match
    for legacy, canonical in LEGACY_EDGE_MAP.items():
        if legacy.lower() == lower:
            return canonical

    return None


def validate_node(node: Dict) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate a single node dict against the ontology.

    Args:
        node: Dict with at least ``{"name": str, "type": str}`` keys.

    Returns:
        ``(is_valid, canonical_type, error_message)`` where *is_valid* is
        ``True`` when the node type resolves to a canonical Schema.org type.
        *canonical_type* is the resolved type (or ``None``).
        *error_message* is populated only when *is_valid* is ``False``.
    """
    raw_type = node.get("type", "")
    canonical = validate_node_type(raw_type)
    if canonical:
        return True, canonical, None
    return (
        False,
        None,
        f"Unknown node type '{raw_type}' for entity '{node.get('name', '?')}'",
    )


def validate_edge(edge: Dict) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate a single edge dict against the ontology.

    Args:
        edge: Dict with at least ``{"from": str, "relation": str, "to": str}``
              keys (or ``"subject"``/``"predicate"``/``"object"`` aliases).

    Returns:
        ``(is_valid, canonical_relation, error_message)``.
    """
    raw_rel = (
        edge.get("relation")
        or edge.get("predicate")
        or edge.get("type")
        or ""
    )
    canonical = validate_edge_type(raw_rel)
    if canonical:
        return True, canonical, None
    src = edge.get("from") or edge.get("subject") or "?"
    tgt = edge.get("to") or edge.get("object") or "?"
    return (
        False,
        None,
        f"Unknown edge type '{raw_rel}' on relation '{src}' → '{tgt}'",
    )


# ---------------------------------------------------------------------------
# System prompt generator
# ---------------------------------------------------------------------------

def generate_ontology_system_prompt() -> str:
    """Generate a system prompt that enforces ontological compliance in LLMs.

    The prompt instructs the model to use *only* the canonical Schema.org node
    types and PROV-O edge types defined in :data:`CORE_ONTOLOGY` and to return
    strictly valid JSON.

    Returns:
        A multi-line string suitable for use as the ``system`` message in an
        LLM chat prompt.
    """
    node_list = "\n".join(
        f"  - {name}: {meta['description']}"
        for name, meta in CORE_ONTOLOGY["NODES"].items()
    )
    edge_list = "\n".join(
        f"  - {name}: {meta['description']}"
        for name, meta in CORE_ONTOLOGY["EDGES"].items()
    )

    return f"""You are an expert knowledge-graph builder operating under strict ontological constraints.

## Ontology Schema

### Allowed Node Types (Schema.org)
{node_list}

### Allowed Relationship Types (PROV-O)
{edge_list}

## Output Requirements

Return ONLY valid JSON with this exact structure:
{{
  "entities": [
    {{
      "name": "<entity name>",
      "type": "<one of the allowed node types above>",
      "description": "<brief factual description>",
      "confidence": <float 0.0–1.0>
    }}
  ],
  "relations": [
    {{
      "from": "<source entity name>",
      "relation": "<one of the allowed relationship types above>",
      "to": "<target entity name>",
      "weight": <float 0.0–1.0>
    }}
  ]
}}

## Strict Rules
1. ONLY use node types from the allowed list above. Do NOT invent new types.
2. ONLY use relationship types from the allowed list above.
3. If an entity does not fit any canonical type, use the closest match.
4. confidence and weight must be floats between 0.0 and 1.0.
5. Focus on the 10 most important entities and 8 most important relationships.
6. Extract causal relationships wherever possible (caused_by, impacts, signals).
7. Do NOT include raw text, explanations, or markdown outside the JSON block.
"""


# ---------------------------------------------------------------------------
# Convenience helpers for downstream validation reports
# ---------------------------------------------------------------------------

def build_validation_report(
    raw_entities: List[Dict],
    raw_relations: List[Dict],
) -> Dict:
    """Validate a full extraction result and build a structured report.

    Args:
        raw_entities: List of entity dicts from the LLM.
        raw_relations: List of relation dicts from the LLM.

    Returns:
        A dict with keys:
        - ``valid_entities``:   list of entities with ``type`` remapped to canonical
        - ``invalid_entities``: list of entities whose type could not be resolved
        - ``valid_edges``:      list of edges with ``relation`` remapped to canonical
        - ``invalid_edges``:    list of edges whose relation could not be resolved
        - ``unmapped_nodes``:   set of entity names with unresolved types
        - ``validation_summary``: human-readable summary string
    """
    valid_entities: List[Dict] = []
    invalid_entities: List[Dict] = []
    unmapped_nodes: List[str] = []

    for entity in raw_entities:
        is_valid, canonical, error = validate_node(entity)
        if is_valid:
            remapped = dict(entity)
            remapped["type"] = canonical
            valid_entities.append(remapped)
        else:
            invalid_entities.append({**entity, "validation_error": error})
            unmapped_nodes.append(entity.get("name", "?"))

    valid_edges: List[Dict] = []
    invalid_edges: List[Dict] = []

    for edge in raw_relations:
        is_valid, canonical, error = validate_edge(edge)
        if is_valid:
            remapped = dict(edge)
            # Normalise relation key
            remapped["relation"] = canonical
            if "predicate" in remapped:
                remapped["predicate"] = canonical
            valid_edges.append(remapped)
        else:
            invalid_edges.append({**edge, "validation_error": error})

    total_in = len(raw_entities) + len(raw_relations)
    total_valid = len(valid_entities) + len(valid_edges)
    compliance_pct = (total_valid / total_in * 100) if total_in else 100.0

    summary = (
        f"Ontology validation: {len(valid_entities)}/{len(raw_entities)} entities valid, "
        f"{len(valid_edges)}/{len(raw_relations)} edges valid "
        f"({compliance_pct:.1f}% ontological compliance)."
    )

    return {
        "valid_entities": valid_entities,
        "invalid_entities": invalid_entities,
        "valid_edges": valid_edges,
        "invalid_edges": invalid_edges,
        "unmapped_nodes": unmapped_nodes,
        "validation_summary": summary,
        "compliance_pct": round(compliance_pct, 1),
    }
