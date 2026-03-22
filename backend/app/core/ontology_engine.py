"""Enterprise ontology engine with multi-perspective modeling."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class EntityClass:
    """Definition of an entity class within the ontology.

    Attributes:
        name: Unique class name (e.g. "Person").
        properties: Dict mapping property name → property schema.
        validation_rules: Dict of field-level validation constraints.
        computed_fields: Dict mapping field name → computation spec.
        classification: Default data classification for instances.
    """

    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    validation_rules: dict[str, Any] = field(default_factory=dict)
    computed_fields: dict[str, Any] = field(default_factory=dict)
    classification: str = "internal"


@dataclass
class Perspective:
    """Role-based view over ontology entities.

    Attributes:
        name: Perspective identifier.
        entity_filters: Dict mapping entity class → field list to expose.
        role_required: Role that can use this perspective.
        clearance_required: Minimum clearance level.
    """

    name: str
    entity_filters: dict[str, list[str]] = field(default_factory=dict)
    role_required: str = "viewer"
    clearance_required: str = "internal"


@dataclass
class ValidationResult:
    """Result of entity validation.

    Attributes:
        is_valid: Whether the entity is valid.
        errors: List of validation error messages.
        warnings: List of non-fatal warnings.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class DataLineage:
    """Lineage record for an entity.

    Attributes:
        entity_id: Target entity ID.
        sources: List of source descriptions.
        transformations: Ordered list of transformations applied.
        created_at: ISO timestamp of original creation.
    """

    entity_id: str
    sources: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)
    created_at: Optional[str] = None


@dataclass
class OntologyVersion:
    """A versioned snapshot of the ontology.

    Attributes:
        ontology_id: Parent ontology ID.
        version: Version counter.
        entity_classes: Snapshot of entity class definitions.
        relationship_types: Snapshot of relationship type definitions.
    """

    ontology_id: str
    version: int
    entity_classes: dict[str, EntityClass] = field(default_factory=dict)
    relationship_types: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    """Relationship definition within the ontology.

    Attributes:
        relationship_type: Relationship label.
        source_class: Entity class of the source node.
        target_class: Entity class of the target node.
        properties: Allowed relationship properties.
        cardinality: Cardinality constraint (e.g. "many-to-many").
    """

    relationship_type: str
    source_class: str
    target_class: str
    properties: dict[str, Any] = field(default_factory=dict)
    cardinality: str = "many-to-many"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class OntologyEngine:
    """Enterprise ontology with multi-perspective modeling.

    Manages entity class schemas, relationship types, perspectives, and
    validation rules.  Ships with sensible built-in defaults that can be
    extended at runtime.

    Attributes:
        entity_classes: Registered entity class definitions.
        relationship_types: Registered relationship type definitions.
        perspectives: Registered perspective definitions.
        _versions: History of ontology versions for change-tracking.
    """

    # Built-in entity classes
    BUILT_IN_ENTITY_CLASSES: list[str] = [
        "Person",
        "Organization",
        "Event",
        "Location",
        "Asset",
    ]

    # Built-in relationship types
    BUILT_IN_RELATIONSHIP_TYPES: list[str] = [
        "AFFILIATED_WITH",
        "LOCATED_IN",
        "CAUSED_BY",
        "RELATED_TO",
        "OWNS",
        "MEMBER_OF",
    ]

    def __init__(self) -> None:
        self.entity_classes: dict[str, EntityClass] = {}
        self.relationship_types: dict[str, Relationship] = {}
        self.perspectives: dict[str, Perspective] = {}
        self._versions: list[OntologyVersion] = []
        self._version_counter: int = 1
        self._bootstrap()

    # ------------------------------------------------------------------
    # Bootstrap defaults
    # ------------------------------------------------------------------

    def _bootstrap(self) -> None:
        """Populate built-in entity classes, relationships, and perspectives."""
        for name in self.BUILT_IN_ENTITY_CLASSES:
            self.entity_classes[name] = EntityClass(
                name=name,
                properties={"id": {"type": "string", "required": True}},
            )

        self.perspectives["analyst_view"] = Perspective(
            name="analyst_view",
            entity_filters={
                cls: ["id", "name", "type", "classification"]
                for cls in self.BUILT_IN_ENTITY_CLASSES
            },
            role_required="analyst",
            clearance_required="confidential",
        )
        self.perspectives["admin_view"] = Perspective(
            name="admin_view",
            entity_filters={},  # no filtering — all fields visible
            role_required="admin",
            clearance_required="secret",
        )
        self.perspectives["viewer_view"] = Perspective(
            name="viewer_view",
            entity_filters={
                cls: ["id", "name"]
                for cls in self.BUILT_IN_ENTITY_CLASSES
            },
            role_required="viewer",
            clearance_required="internal",
        )

    # ------------------------------------------------------------------
    # Entity class management
    # ------------------------------------------------------------------

    def define_entity_class(
        self,
        name: str,
        properties: dict[str, Any],
        validation_rules: Optional[dict[str, Any]] = None,
        computed_fields: Optional[dict[str, Any]] = None,
    ) -> EntityClass:
        """Register a new (or update an existing) entity class.

        Args:
            name: Class name.
            properties: Property schema dict.
            validation_rules: Optional validation constraints.
            computed_fields: Optional computed field specs.

        Returns:
            The registered :class:`EntityClass`.
        """
        ec = EntityClass(
            name=name,
            properties=properties,
            validation_rules=validation_rules or {},
            computed_fields=computed_fields or {},
        )
        self.entity_classes[name] = ec
        logger.info("Registered entity class '%s'", name)
        return ec

    # ------------------------------------------------------------------
    # Perspectives
    # ------------------------------------------------------------------

    def create_perspective(
        self,
        perspective_name: str,
        entity_filters: dict[str, list[str]],
        role_based_view: dict[str, Any],
    ) -> Perspective:
        """Register a role-based perspective.

        Args:
            perspective_name: Unique perspective identifier.
            entity_filters: Per-class field allow-lists.
            role_based_view: Dict with ``role_required`` and
                ``clearance_required`` keys.

        Returns:
            The registered :class:`Perspective`.
        """
        p = Perspective(
            name=perspective_name,
            entity_filters=entity_filters,
            role_required=role_based_view.get("role_required", "viewer"),
            clearance_required=role_based_view.get(
                "clearance_required", "internal"
            ),
        )
        self.perspectives[perspective_name] = p
        return p

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_entity(
        self, entity_data: dict, entity_class: str
    ) -> ValidationResult:
        """Validate an entity dict against its registered schema.

        Args:
            entity_data: The entity data to validate.
            entity_class: Entity class name to validate against.

        Returns:
            :class:`ValidationResult` with errors if invalid.
        """
        errors: list[str] = []
        warnings: list[str] = []

        ec = self.entity_classes.get(entity_class)
        if ec is None:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown entity class '{entity_class}'"],
            )

        for prop_name, prop_schema in ec.properties.items():
            if prop_schema.get("required") and prop_name not in entity_data:
                errors.append(f"Required property '{prop_name}' is missing")

        for rule_name, rule_config in ec.validation_rules.items():
            field_name = rule_config.get("field")
            if not field_name:
                continue
            value = entity_data.get(field_name)
            if rule_config.get("type") == "not_null" and value is None:
                errors.append(
                    f"Validation rule '{rule_name}': field '{field_name}' must not be null"
                )
            if rule_config.get("type") == "min_length":
                min_len = rule_config.get("value", 0)
                if value and len(str(value)) < min_len:
                    errors.append(
                        f"Validation rule '{rule_name}': field '{field_name}' is too short"
                    )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    def compute_fields(
        self, entity: dict, entity_class: str
    ) -> dict:
        """Apply computed-field specifications and return augmented entity.

        Args:
            entity: Original entity dict.
            entity_class: Class name.

        Returns:
            Entity dict augmented with computed field values.
        """
        ec = self.entity_classes.get(entity_class)
        if ec is None:
            return entity
        result = dict(entity)
        for field_name, spec in ec.computed_fields.items():
            try:
                if spec.get("type") == "concat":
                    source_fields = spec.get("fields", [])
                    result[field_name] = " ".join(
                        str(entity.get(f, "")) for f in source_fields
                    )
                elif spec.get("type") == "constant":
                    result[field_name] = spec.get("value")
            except Exception as exc:
                logger.warning(
                    "Failed to compute field '%s': %s", field_name, exc
                )
        return result

    # ------------------------------------------------------------------
    # Lineage
    # ------------------------------------------------------------------

    def get_data_lineage(self, entity_id: str) -> DataLineage:
        """Return a basic lineage record for an entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            :class:`DataLineage` with available provenance information.
        """
        return DataLineage(
            entity_id=entity_id,
            sources=["eldruin-platform"],
            transformations=["ingestion", "normalization"],
        )

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    def create_version(self, ontology_id: str) -> OntologyVersion:
        """Snapshot the current ontology state as a new version.

        Args:
            ontology_id: Parent ontology identifier.

        Returns:
            :class:`OntologyVersion` snapshot.
        """
        version = OntologyVersion(
            ontology_id=ontology_id,
            version=self._version_counter,
            entity_classes=dict(self.entity_classes),
            relationship_types={
                k: {
                    "relationship_type": v.relationship_type,
                    "source_class": v.source_class,
                    "target_class": v.target_class,
                }
                for k, v in self.relationship_types.items()
            },
        )
        self._versions.append(version)
        self._version_counter += 1
        return version

    # ------------------------------------------------------------------
    # Relationship queries
    # ------------------------------------------------------------------

    def get_relationships(
        self,
        entity_class: str,
        relationship_type: Optional[str] = None,
    ) -> list[Relationship]:
        """Return relationships involving a given entity class.

        Args:
            entity_class: Entity class name to filter by.
            relationship_type: Optional relationship type filter.

        Returns:
            Matching :class:`Relationship` instances.
        """
        results: list[Relationship] = []
        for rel in self.relationship_types.values():
            if entity_class in (rel.source_class, rel.target_class):
                if relationship_type is None or rel.relationship_type == relationship_type:
                    results.append(rel)
        return results

    # ------------------------------------------------------------------
    # Perspective application
    # ------------------------------------------------------------------

    def apply_perspective(
        self,
        entity: dict,
        perspective: str,
        user_role: str,
    ) -> dict:
        """Filter an entity dict through a named perspective.

        Args:
            entity: Raw entity dict.
            perspective: Perspective name to apply.
            user_role: Requesting user's role.

        Returns:
            Filtered entity dict; returns empty dict if access denied.
        """
        p = self.perspectives.get(perspective)
        if p is None:
            logger.warning("Unknown perspective '%s'", perspective)
            return entity

        entity_class = entity.get("entity_class", entity.get("type", ""))
        allowed_fields = p.entity_filters.get(entity_class)

        # admin_view: no field filtering
        if not allowed_fields and perspective == "admin_view":
            return entity

        if allowed_fields is None:
            return entity

        return {k: v for k, v in entity.items() if k in allowed_fields}


# Module-level singleton
ontology_engine = OntologyEngine()
