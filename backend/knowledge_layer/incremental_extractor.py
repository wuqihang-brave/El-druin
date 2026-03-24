"""
Incremental GraphRAG Extraction Logic
======================================

Implements intelligent delta updates instead of simple insert-or-overwrite
operations.  Before inserting new entities/relations, existing similar nodes
are queried and conflict detection determines whether to merge, update, or
create a ``CONTRADICTS`` relationship.

Key functions
-------------

* :func:`find_similar_entities` – fuzzy-match existing nodes; returns
  candidate matches with confidence scores.
* :func:`detect_conflict` – check whether two relations semantically
  contradict each other.
* :func:`create_contradicts_edge` – persist a CONTRADICTS edge between two
  entity nodes.
* :func:`incremental_update` – orchestrate the full incremental update flow
  and return summary metrics.

Few-shot causal prompt
----------------------

:data:`FEW_SHOT_CAUSAL_PROMPT` is a ready-to-use system prompt string that
can be injected into any LangChain chain to bias extraction toward
"A causes B" causal links rather than static entity descriptions.

Usage example::

    from knowledge_layer.incremental_extractor import incremental_update

    summary = incremental_update(
        entities=[{"name": "Federal Reserve", "type": "ORG"}],
        relations=[{"from": "Federal Reserve", "relation": "raises",
                    "to": "interest rates", "weight": 0.9}],
        source_reliability=0.85,
        source_url="https://example.com/news/fed-raises-rates",
    )
    print(summary)
    # {
    #   "entities_added": 1, "entities_merged": 0,
    #   "relations_added": 1, "conflicts_found": 0,
    #   "contradicts_created": 0, "contradictions": []
    # }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

#: Minimum similarity ratio to treat two entity names as the same real-world
#: entity and trigger conflict-checking logic.
ENTITY_SIMILARITY_THRESHOLD: float = 0.85

#: Known semantically-opposing relation type pairs.  When an existing edge
#: uses one predicate and a new edge uses the other (for the same entity pair),
#: they are treated as contradictory.
_CONTRADICTING_PAIRS: List[tuple] = [
    ("raises", "cuts"),
    ("raises", "lowers"),
    ("increases", "decreases"),
    ("supports", "opposes"),
    ("supports", "condemns"),
    ("invades", "withdraws_from"),
    ("expands", "reduces"),
    ("accelerates", "decelerates"),
    ("approves", "rejects"),
    ("launches", "cancels"),
    ("agrees_with", "opposes"),
    ("acquires", "divests"),
    ("hires", "fires"),
    ("builds", "destroys"),
    ("imposes", "lifts"),
    ("escalates", "de-escalates"),
]

# Pre-build a flat set of ordered (a, b) and (b, a) pairs for O(1) lookup.
_CONTRADICTING_SET: set = set()
for _a, _b in _CONTRADICTING_PAIRS:
    _CONTRADICTING_SET.add((_a, _b))
    _CONTRADICTING_SET.add((_b, _a))


# ---------------------------------------------------------------------------
# Few-shot causal extraction prompt
# ---------------------------------------------------------------------------

FEW_SHOT_CAUSAL_PROMPT: str = """\
You are a knowledge-graph builder specializing in CAUSAL relationship extraction.
Extract entities and causal relations from the given text.
Focus on "A causes / leads to / results in B" patterns rather than static descriptions.

---

### Example 1: Policy change → economic impact

Text: "The Federal Reserve raised interest rates by 75 basis points, causing \
mortgage costs to surge and housing market activity to drop sharply."

Output:
{
  "entities": [
    {"name": "Federal Reserve",  "type": "ORG",     "description": "US central bank",              "confidence": 0.95},
    {"name": "interest rates",   "type": "CONCEPT", "description": "monetary policy instrument",   "confidence": 0.90},
    {"name": "mortgage costs",   "type": "CONCEPT", "description": "cost of home loans",           "confidence": 0.85},
    {"name": "housing market",   "type": "CONCEPT", "description": "real estate sector activity",  "confidence": 0.85}
  ],
  "relations": [
    {"from": "Federal Reserve", "relation": "raises",          "to": "interest rates", "weight": 0.95},
    {"from": "interest rates",  "relation": "causes_surge_in", "to": "mortgage costs", "weight": 0.90},
    {"from": "interest rates",  "relation": "depresses",       "to": "housing market", "weight": 0.85}
  ]
}

---

### Example 2: Event occurrence → organizational response

Text: "Following the earthquake in Turkey, NATO deployed emergency response \
teams and the Red Cross mobilized 500 volunteers."

Output:
{
  "entities": [
    {"name": "Turkey earthquake", "type": "EVENT", "description": "natural disaster in Turkey",    "confidence": 0.95},
    {"name": "Turkey",           "type": "GPE",   "description": "country affected",              "confidence": 0.95},
    {"name": "NATO",             "type": "ORG",   "description": "military alliance",             "confidence": 0.90},
    {"name": "Red Cross",        "type": "ORG",   "description": "humanitarian organisation",     "confidence": 0.90}
  ],
  "relations": [
    {"from": "Turkey earthquake", "relation": "triggers_response_from", "to": "NATO",      "weight": 0.90},
    {"from": "Turkey earthquake", "relation": "triggers_response_from", "to": "Red Cross", "weight": 0.90},
    {"from": "NATO",              "relation": "deploys_to",             "to": "Turkey",    "weight": 0.85}
  ]
}

---

### Example 3: Person's action → consequence on other entities

Text: "Elon Musk's acquisition of Twitter led to a mass advertiser exodus \
and a significant decline in platform revenue."

Output:
{
  "entities": [
    {"name": "Elon Musk",       "type": "PERSON", "description": "tech entrepreneur",           "confidence": 0.95},
    {"name": "Twitter",         "type": "ORG",    "description": "social media platform",       "confidence": 0.95},
    {"name": "advertisers",     "type": "ORG",    "description": "revenue sources on Twitter",  "confidence": 0.85},
    {"name": "Twitter revenue", "type": "CONCEPT","description": "platform advertising income", "confidence": 0.80}
  ],
  "relations": [
    {"from": "Elon Musk",   "relation": "acquires",           "to": "Twitter",         "weight": 0.95},
    {"from": "Elon Musk",   "relation": "causes_exodus_of",   "to": "advertisers",     "weight": 0.85},
    {"from": "advertisers", "relation": "reduces",            "to": "Twitter revenue", "weight": 0.85}
  ]
}

---

Now analyze the following text and return ONLY valid JSON with the exact same
structure (entities + relations arrays). Each relation weight should reflect
how strongly causal the relationship is (1.0 = direct cause, 0.5 = indirect
influence). Limit to the 10 most important entities and 8 most important
relations. confidence must be a float between 0.0 and 1.0.\
"""


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _similarity(a: str, b: str) -> float:
    """Return a normalised similarity ratio in [0.0, 1.0] between two strings."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


# ---------------------------------------------------------------------------
# Core public functions
# ---------------------------------------------------------------------------

def find_similar_entities(
    entity_name: str,
    entity_type: str,
    store: Any,
    threshold: float = ENTITY_SIMILARITY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Find existing graph entities similar to *entity_name*.

    Uses :func:`difflib.SequenceMatcher` to compute string similarity ratios
    between *entity_name* and every entity currently stored in *store*.

    Parameters
    ----------
    entity_name:
        The name of the new entity to match against.
    entity_type:
        The type of the new entity (informational; not used to filter results
        so that cross-type matches are still surfaced).
    store:
        Any object with a ``get_entities(limit: int)`` method that returns a
        list of dicts containing at least ``name`` and ``type`` keys.
    threshold:
        Similarity ratio above which a candidate is flagged as a potential
        conflict (``is_conflict = True``).  Defaults to
        :data:`ENTITY_SIMILARITY_THRESHOLD` (0.85).

    Returns
    -------
    list[dict]
        Up to 10 candidate matches sorted by similarity descending.  Each
        item contains:

        * ``name``         – name of the existing entity
        * ``type``         – type of the existing entity
        * ``description``  – description of the existing entity (may be empty)
        * ``similarity``   – float similarity ratio in [0.0, 1.0]
        * ``is_conflict``  – ``True`` when similarity ≥ *threshold*

    Examples
    --------
    ::

        candidates = find_similar_entities("Federal Reserve", "ORG", store)
        for c in candidates:
            print(c["name"], c["similarity"], c["is_conflict"])
    """
    try:
        existing: List[Dict[str, Any]] = store.get_entities(limit=10000)
    except Exception as exc:
        logger.warning("find_similar_entities: could not fetch entities – %s", exc)
        return []

    candidates: List[Dict[str, Any]] = []
    for entity in existing:
        name = entity.get("name", "")
        if not name:
            continue
        sim = _similarity(entity_name, name)
        if sim > 0.0:
            candidates.append(
                {
                    "name": name,
                    "type": entity.get("type", ""),
                    "description": entity.get("description", ""),
                    "similarity": round(sim, 4),
                    "is_conflict": sim >= threshold,
                }
            )

    candidates.sort(key=lambda x: x["similarity"], reverse=True)
    return candidates[:10]


def detect_conflict(
    old_relation: Dict[str, Any],
    new_relation: Dict[str, Any],
) -> bool:
    """Return ``True`` when *new_relation* semantically contradicts *old_relation*.

    Two relations are considered contradictory when:

    1. They share the same subject–object pair (or its reverse), **and**
    2. Their predicate / relation type is one of the known opposing pairs
       defined in :data:`_CONTRADICTING_SET`.

    Parameters
    ----------
    old_relation:
        Dict with keys ``subject`` (or ``from``), ``predicate`` (or
        ``relation``), and ``object`` (or ``to``).
    new_relation:
        Same structure as *old_relation*.

    Returns
    -------
    bool

    Examples
    --------
    ::

        old = {"subject": "Fed", "predicate": "raises", "object": "rates"}
        new = {"subject": "Fed", "predicate": "cuts",   "object": "rates"}
        assert detect_conflict(old, new) is True
    """

    def _get(rel: Dict[str, Any], key: str, fallback: str) -> str:
        return str(rel.get(key, rel.get(fallback, ""))).lower().strip()

    old_subj = _get(old_relation, "subject", "from")
    old_pred = _get(old_relation, "predicate", "relation")
    old_obj  = _get(old_relation, "object",  "to")

    new_subj = _get(new_relation, "subject", "from")
    new_pred = _get(new_relation, "predicate", "relation")
    new_obj  = _get(new_relation, "object",  "to")

    # Entities must share the same subject/object pair (in either direction).
    same_endpoints = (
        (old_subj == new_subj and old_obj == new_obj)
        or (old_subj == new_obj and old_obj == new_subj)
    )
    if not same_endpoints:
        return False

    return (old_pred, new_pred) in _CONTRADICTING_SET


def create_contradicts_edge(
    store: Any,
    entity1_name: str,
    entity2_name: str,
    reason: str,
    confidence: float = 0.8,
    source_reliability: float = 0.7,
) -> bool:
    """Persist a CONTRADICTS edge between two entity nodes in *store*.

    Parameters
    ----------
    store:
        A ``GraphStore`` (or ``KnowledgeGraph``) instance exposing an
        ``add_contradicts`` method.
    entity1_name:
        Name of the first entity node (source of the directed edge).
    entity2_name:
        Name of the second entity node (target of the directed edge).
    reason:
        Human-readable explanation of the contradiction.
    confidence:
        Confidence that this is a genuine contradiction (0.0–1.0).
    source_reliability:
        Reliability of the source that reported the contradicting fact.

    Returns
    -------
    bool
        ``True`` on success, ``False`` on failure.

    Examples
    --------
    ::

        ok = create_contradicts_edge(
            store, "Federal Reserve", "ECB",
            reason="Fed raises rates while ECB cuts rates",
        )
    """
    try:
        store.add_contradicts(
            from_name=entity1_name,
            to_name=entity2_name,
            reason=reason,
            confidence=confidence,
            source_reliability=source_reliability,
        )
        logger.info(
            "CONTRADICTS edge created: %r ↔ %r  reason=%r",
            entity1_name,
            entity2_name,
            reason,
        )
        return True
    except Exception as exc:
        logger.warning(
            "create_contradicts_edge(%r, %r): %s",
            entity1_name,
            entity2_name,
            exc,
        )
        return False


def incremental_update(
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    source_reliability: float = 0.7,
    source_url: str = "",
    store: Optional[Any] = None,
    similarity_threshold: float = ENTITY_SIMILARITY_THRESHOLD,
) -> Dict[str, Any]:
    """Orchestrate the incremental knowledge-graph update flow.

    For each extracted entity this function:

    1. Queries the store for fuzzy-similar existing nodes.
    2. If no similar node exists → inserts normally.
    3. If a similar node exists (similarity ≥ *similarity_threshold*) →
       treats it as the canonical node (merge); skips re-insertion.
    4. For each extracted relation, checks whether an existing relation
       contradicts it (via :func:`detect_conflict`).
    5. If a contradiction is found → creates a ``CONTRADICTS`` edge and
       logs the conflict; the new relation is **not** inserted.
    6. If no contradiction → inserts the new relation normally.

    Parameters
    ----------
    entities:
        List of entity dicts, each with at least ``name`` and ``type`` keys.
    relations:
        List of relation dicts, each with ``from``/``subject``,
        ``relation``/``predicate``, and ``to``/``object`` keys.
    source_reliability:
        Reliability of the data source (0.0–1.0).  Included in CONTRADICTS
        edges for audit purposes.
    source_url:
        URL of the source article (informational only; included in
        contradiction audit records).
    store:
        GraphStore or KnowledgeGraph instance to use.  When ``None``, the
        default singleton is loaded via ``get_knowledge_graph()``.
    similarity_threshold:
        Entities with a similarity ratio above this value are considered to
        refer to the same real-world node (default: 0.85).

    Returns
    -------
    dict
        Summary with the following integer/list keys:

        * ``entities_added``      – new entity nodes inserted
        * ``entities_merged``     – entities matched to an existing node
        * ``relations_added``     – new relation edges inserted
        * ``conflicts_found``     – relation contradictions detected
        * ``contradicts_created`` – CONTRADICTS edges successfully written
        * ``contradictions``      – list of contradiction detail dicts

    Examples
    --------
    ::

        summary = incremental_update(
            entities=[{"name": "Federal Reserve", "type": "ORG"}],
            relations=[{"from": "Federal Reserve", "relation": "raises",
                        "to": "interest rates", "weight": 0.9}],
            source_reliability=0.85,
            source_url="https://example.com/article",
        )
        print(summary["entities_added"], summary["conflicts_found"])
    """
    if store is None:
        from app.knowledge.knowledge_graph import get_knowledge_graph
        store = get_knowledge_graph()

    entities_added = 0
    entities_merged = 0
    relations_added = 0
    conflicts_found = 0
    contradicts_created = 0
    contradictions: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Phase 1 – Entity disambiguation and insertion
    # ------------------------------------------------------------------
    # Maps each incoming entity name to its canonical name (either the
    # matched existing name or itself if newly inserted).
    entity_name_map: Dict[str, str] = {}

    for entity in entities:
        name = entity.get("name", "").strip()
        if not name:
            continue

        entity_type = entity.get("type", "MISC")
        description = entity.get("description", "")

        candidates = find_similar_entities(
            name, entity_type, store, threshold=similarity_threshold
        )
        high_confidence_match = next(
            (c for c in candidates if c["is_conflict"]), None
        )

        if high_confidence_match:
            # Entity already exists under a (possibly slightly different) name.
            canonical = high_confidence_match["name"]
            entity_name_map[name] = canonical
            entities_merged += 1
            logger.debug(
                "Entity %r merged with existing %r (similarity=%.2f)",
                name,
                canonical,
                high_confidence_match["similarity"],
            )
        else:
            entity_name_map[name] = name
            try:
                store.add_entity(name, entity_type, description)
                entities_added += 1
            except Exception as exc:
                logger.debug("incremental_update add_entity(%r): %s", name, exc)

    # ------------------------------------------------------------------
    # Phase 2 – Relation conflict detection and insertion
    # ------------------------------------------------------------------
    try:
        existing_relations: List[Dict[str, Any]] = store.get_relations(limit=5000)
    except Exception as exc:
        logger.warning("incremental_update: could not fetch relations – %s", exc)
        existing_relations = []

    for new_rel in relations:
        raw_from = new_rel.get("from", new_rel.get("subject", "")).strip()
        raw_to   = new_rel.get("to",   new_rel.get("object",  "")).strip()
        rel_type = (
            new_rel.get("relation", new_rel.get("predicate", "related_to"))
            .strip()
        )

        if not raw_from or not raw_to:
            continue

        # Normalise names to their canonical form determined in Phase 1.
        from_name = entity_name_map.get(raw_from, raw_from)
        to_name   = entity_name_map.get(raw_to,   raw_to)

        norm_new = {"subject": from_name, "predicate": rel_type, "object": to_name}

        conflict_detected = False
        for old_rel in existing_relations:
            norm_old = {
                "subject":   old_rel.get("from", ""),
                "predicate": old_rel.get("relation", ""),
                "object":    old_rel.get("to", ""),
            }
            if detect_conflict(norm_old, norm_new):
                conflict_detected = True
                conflicts_found += 1
                reason = (
                    f"New relation '{from_name} {rel_type} {to_name}' contradicts "
                    f"existing '{norm_old['subject']} {norm_old['predicate']} "
                    f"{norm_old['object']}' (source: {source_url or 'unknown'})"
                )
                logger.info("Conflict detected: %s", reason)

                ok = create_contradicts_edge(
                    store,
                    entity1_name=from_name,
                    entity2_name=to_name,
                    reason=reason,
                    confidence=0.8,
                    source_reliability=source_reliability,
                )
                if ok:
                    contradicts_created += 1

                contradictions.append(
                    {
                        "new_relation": norm_new,
                        "old_relation": norm_old,
                        "reason": reason,
                        "source_url": source_url,
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )
                break  # One CONTRADICTS edge per incoming relation is sufficient.

        if not conflict_detected:
            try:
                store.add_relation(
                    from_name=from_name,
                    from_type="MISC",
                    to_name=to_name,
                    to_type="MISC",
                    relation_type=rel_type,
                    weight=float(new_rel.get("weight", 0.5)),
                )
                relations_added += 1
            except Exception as exc:
                logger.debug(
                    "incremental_update add_relation(%r→%r): %s",
                    from_name,
                    to_name,
                    exc,
                )

    return {
        "entities_added": entities_added,
        "entities_merged": entities_merged,
        "relations_added": relations_added,
        "conflicts_found": conflicts_found,
        "contradicts_created": contradicts_created,
        "contradictions": contradictions,
    }
