"""
Global Entity Resolver
======================

Implements Object-Centric Ontology entity deduplication and merging using
fuzzy name matching.  Every entity carries a ``property_history`` JSON field
that records all property changes over time.

Key design points
-----------------

* **Exact ID match** → merge immediately (return existing entity).
* **Fuzzy name + type match, similarity > threshold** → auto-merge and log.
* **No match** → create a new entity with empty ``property_history``.
* **Property history** – every change is appended to the entity's
  ``property_history`` list with timestamp, old/new values, source reference,
  and confidence.

Usage::

    from knowledge_layer.entity_resolver import GlobalEntityResolver

    resolver = GlobalEntityResolver(store)
    entity_id = resolver.resolve_entity(
        entity_name="Federal Reserve",
        entity_type="Organization",
        properties={"order_index": 85, "risk_level": "high"},
        source_ref="article-hash-abc123",
    )
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Similarity threshold above which two entities are considered the same and
#: will be auto-merged.
SIMILARITY_THRESHOLD: float = 0.85


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _similarity(a: str, b: str) -> float:
    """Return normalised similarity ratio between two strings (case-insensitive)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class Match:
    """A candidate entity match returned by :meth:`GlobalEntityResolver.find_similar_entities`."""

    def __init__(
        self,
        entity_id: str,
        entity_name: str,
        entity_type: str,
        similarity: float,
        auto_merge: bool,
    ) -> None:
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.entity_type = entity_type
        self.similarity = similarity
        #: True when similarity exceeds the auto-merge threshold.
        self.auto_merge = auto_merge

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "similarity": self.similarity,
            "auto_merge": self.auto_merge,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Match(entity_id={self.entity_id!r}, name={self.entity_name!r}, "
            f"type={self.entity_type!r}, similarity={self.similarity:.3f}, "
            f"auto_merge={self.auto_merge})"
        )


# ---------------------------------------------------------------------------
# GlobalEntityResolver
# ---------------------------------------------------------------------------


class GlobalEntityResolver:
    """Deduplicates and merges entities using fuzzy name matching.

    Parameters
    ----------
    store:
        A storage backend that exposes at minimum the following interface:

        * ``get_entities(limit=1000) → List[Dict]``
          – each dict must contain ``"id"``, ``"name"``, ``"type"``, and
            ``"property_history"`` (JSON string) keys.
        * ``upsert_entity(id, name, entity_type, properties) → None``
          – create-or-replace the entity record.
        * ``get_entity_by_id(entity_id) → Optional[Dict]``
          – return ``None`` when entity is not found.

        Pass ``None`` to use an in-memory dictionary store (useful in tests).

    similarity_threshold:
        Minimum similarity score (0.0–1.0) required to trigger auto-merging.
        Defaults to :data:`SIMILARITY_THRESHOLD` (0.85).
    """

    def __init__(
        self,
        store: Any = None,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ) -> None:
        self._store = store
        self._threshold = similarity_threshold

        # In-memory fallback used when no persistent store is provided.
        self._memory: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_entity(
        self,
        entity_name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None,
        source_ref: str = "",
    ) -> str:
        """Resolve an entity: find an existing match or create a new one.

        Parameters
        ----------
        entity_name:
            Human-readable name of the entity.
        entity_type:
            Ontology type (e.g. ``"Person"``, ``"Organization"``).
        properties:
            Additional properties to attach to the entity (e.g. order_index,
            risk_level).
        source_ref:
            Identifier of the source article/document (used in property
            history entries).

        Returns
        -------
        str
            The ``entity_id`` of the resolved entity (either existing or
            newly created).
        """
        if not entity_name or not entity_name.strip():
            raise ValueError("entity_name must be a non-empty string")

        properties = properties or {}

        # 1. Search for similar existing entities.
        candidates = self.find_similar_entities(entity_name, entity_type)

        # 2. Check for exact ID match first.
        supplied_id = properties.get("id", "")
        if supplied_id:
            existing = self._get_entity_by_id(supplied_id)
            if existing:
                logger.debug(
                    "Exact ID match for %r → %s; updating properties.", entity_name, supplied_id
                )
                self._apply_property_updates(supplied_id, existing, properties, source_ref)
                return supplied_id

        # 3. Auto-merge if a high-similarity candidate is found.
        for match in candidates:
            if match.auto_merge:
                logger.info(
                    "Auto-merging %r into existing entity %r (similarity=%.3f).",
                    entity_name,
                    match.entity_name,
                    match.similarity,
                )
                existing = self._get_entity_by_id(match.entity_id)
                if existing:
                    self._apply_property_updates(match.entity_id, existing, properties, source_ref)
                return match.entity_id

        # 4. No match – create a new entity.
        new_id = str(uuid.uuid4())
        entity_record: Dict[str, Any] = {
            "id": new_id,
            "name": entity_name,
            "type": entity_type,
            "property_history": json.dumps([]),
            **{k: v for k, v in properties.items() if k != "id"},
        }
        self._upsert_entity(new_id, entity_name, entity_type, entity_record)
        logger.info("Created new entity %r (id=%s, type=%s).", entity_name, new_id, entity_type)

        # Record initial properties in history.
        for prop_name, prop_value in properties.items():
            if prop_name == "id":
                continue
            self.update_property_history(
                entity_id=new_id,
                property_name=prop_name,
                old_value=None,
                new_value=prop_value,
                source_ref=source_ref,
                confidence=1.0,
            )

        return new_id

    def find_similar_entities(
        self,
        name: str,
        entity_type: str,
        threshold: Optional[float] = None,
    ) -> List[Match]:
        """Return candidate entities with similarity scores.

        Parameters
        ----------
        name:
            Entity name to search for.
        entity_type:
            Entity type filter (only entities of the same type are considered).
        threshold:
            Override the instance-level threshold for this call.

        Returns
        -------
        list[Match]
            Sorted by similarity descending, at most 10 candidates.
        """
        effective_threshold = threshold if threshold is not None else self._threshold
        all_entities = self._get_all_entities()
        matches: List[Match] = []

        for entity in all_entities:
            existing_name: str = entity.get("name", "")
            existing_type: str = entity.get("type", "")
            existing_id: str = entity.get("id", "")

            if not existing_name or not existing_id:
                continue

            # Type filter: only match same ontology type.
            if existing_type.lower() != entity_type.lower():
                continue

            sim = _similarity(name, existing_name)
            matches.append(
                Match(
                    entity_id=existing_id,
                    entity_name=existing_name,
                    entity_type=existing_type,
                    similarity=sim,
                    auto_merge=sim >= effective_threshold,
                )
            )

        # Sort by similarity descending, limit to 10.
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches[:10]

    def merge_entities(
        self,
        primary_id: str,
        secondary_id: str,
        reasoning: str = "",
    ) -> str:
        """Merge *secondary* into *primary*, preserving full property history.

        After merging:

        * The primary entity retains its ``id``.
        * The secondary entity's ``property_history`` is prepended to the
          primary's history so auditors can see the full lineage.
        * The secondary entity record is removed from the store.

        Parameters
        ----------
        primary_id:
            Entity that will survive the merge.
        secondary_id:
            Entity that will be absorbed into *primary*.
        reasoning:
            Human/LLM-supplied rationale for the merge (stored in history).

        Returns
        -------
        str
            The ``entity_id`` of the surviving (primary) entity.

        Raises
        ------
        KeyError
            If either entity does not exist.
        """
        primary = self._get_entity_by_id(primary_id)
        secondary = self._get_entity_by_id(secondary_id)

        if primary is None:
            raise KeyError(f"Primary entity not found: {primary_id!r}")
        if secondary is None:
            raise KeyError(f"Secondary entity not found: {secondary_id!r}")

        primary_history: List[Dict[str, Any]] = json.loads(primary.get("property_history", "[]"))
        secondary_history: List[Dict[str, Any]] = json.loads(
            secondary.get("property_history", "[]")
        )

        # Append a merge event to the primary's history.
        merge_entry: Dict[str, Any] = {
            "timestamp": _now_iso(),
            "property_name": "_merge",
            "old_value": None,
            "new_value": secondary_id,
            "source_ref": "merge-operation",
            "confidence": 1.0,
            "reasoning": reasoning,
            "merged_from": {
                "id": secondary_id,
                "name": secondary.get("name", ""),
                "type": secondary.get("type", ""),
            },
        }

        # Secondary history comes first (older lineage), then primary, then
        # the new merge event.
        combined_history = secondary_history + primary_history + [merge_entry]

        # Update primary with combined history and secondary's aliases.
        primary["property_history"] = json.dumps(combined_history)
        primary_aliases = primary.get("aliases", [])
        secondary_name = secondary.get("name", "")
        if secondary_name and secondary_name not in primary_aliases:
            primary_aliases.append(secondary_name)
        primary["aliases"] = primary_aliases

        self._upsert_entity(primary_id, primary["name"], primary["type"], primary)

        # Remove secondary from store.
        self._delete_entity(secondary_id)

        logger.info(
            "Merged entity %r into %r (primary_id=%s).",
            secondary.get("name", secondary_id),
            primary.get("name", primary_id),
            primary_id,
        )
        return primary_id

    def update_property_history(
        self,
        entity_id: str,
        property_name: str,
        old_value: Any,
        new_value: Any,
        source_ref: str = "",
        confidence: float = 1.0,
    ) -> None:
        """Append a change record to the entity's ``property_history``.

        Parameters
        ----------
        entity_id:
            ID of the entity to update.
        property_name:
            Name of the property that changed.
        old_value:
            Previous value (``None`` for initial set).
        new_value:
            New value after the change.
        source_ref:
            Article hash or URL that caused the change.
        confidence:
            Confidence score of the extraction (0.0–1.0).
        """
        entity = self._get_entity_by_id(entity_id)
        if entity is None:
            logger.warning(
                "update_property_history called for unknown entity_id=%r; skipping.", entity_id
            )
            return

        history: List[Dict[str, Any]] = json.loads(entity.get("property_history", "[]"))
        history.append(
            {
                "timestamp": _now_iso(),
                "property_name": property_name,
                "old_value": old_value,
                "new_value": new_value,
                "source_ref": source_ref,
                "confidence": float(confidence),
            }
        )
        entity["property_history"] = json.dumps(history)
        self._upsert_entity(entity_id, entity["name"], entity["type"], entity)

    # ------------------------------------------------------------------
    # Storage layer (dispatches to real store or in-memory dict)
    # ------------------------------------------------------------------

    def _get_all_entities(self) -> List[Dict[str, Any]]:
        """Return all entities from the configured store."""
        if self._store is not None:
            try:
                return self._store.get_entities(limit=10000)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to retrieve entities from store: %s", exc)
                return []
        return list(self._memory.values())

    def _get_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Return entity dict or ``None``."""
        if self._store is not None:
            try:
                return self._store.get_entity_by_id(entity_id)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to get entity %r: %s", entity_id, exc)
                return None
        return self._memory.get(entity_id)

    def _upsert_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        record: Dict[str, Any],
    ) -> None:
        """Create or replace entity in the store."""
        if self._store is not None:
            try:
                self._store.upsert_entity(entity_id, name, entity_type, record)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to upsert entity %r: %s", entity_id, exc)
        else:
            self._memory[entity_id] = record

    def _delete_entity(self, entity_id: str) -> None:
        """Remove entity from the store (used during merge)."""
        if self._store is not None:
            try:
                self._store.delete_entity(entity_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to delete entity %r: %s", entity_id, exc)
        else:
            self._memory.pop(entity_id, None)

    def _apply_property_updates(
        self,
        entity_id: str,
        existing: Dict[str, Any],
        new_properties: Dict[str, Any],
        source_ref: str,
    ) -> None:
        """Diff new_properties against existing and record changes in history."""
        changed = False
        for prop_name, new_value in new_properties.items():
            if prop_name in ("id", "property_history"):
                continue
            old_value = existing.get(prop_name)
            if old_value != new_value:
                existing[prop_name] = new_value
                changed = True
                self.update_property_history(
                    entity_id=entity_id,
                    property_name=prop_name,
                    old_value=old_value,
                    new_value=new_value,
                    source_ref=source_ref,
                    confidence=new_properties.get("confidence", 1.0)
                    if prop_name != "confidence"
                    else 1.0,
                )

        if changed:
            self._upsert_entity(entity_id, existing["name"], existing["type"], existing)
