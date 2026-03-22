"""Unit tests for OntologyEngine — aligned to the actual API."""

from __future__ import annotations

import pytest
from app.core.ontology_engine import EntityClass, OntologyEngine, Perspective, ValidationResult


class TestOntologyEngine:
    """Tests for the enterprise ontology engine."""

    def setup_method(self):
        self.engine = OntologyEngine()

    # ------------------------------------------------------------------
    # Entity class definition
    # ------------------------------------------------------------------

    def test_define_entity_class(self):
        """Defining a new entity class stores it in entity_classes."""
        self.engine.define_entity_class(
            name="Vehicle",
            properties={
                "make": {"type": "string"},
                "model": {"type": "string"},
                "year": {"type": "integer"},
            },
        )
        cls = self.engine.entity_classes.get("Vehicle")
        assert cls is not None
        assert cls.name == "Vehicle"
        assert "make" in cls.properties

    def test_define_entity_class_with_validation_rules(self):
        """Validation rules are stored with the entity class."""
        self.engine.define_entity_class(
            name="Asset",
            properties={"value": {"type": "number"}},
            validation_rules={"value_check": {"field": "value", "type": "not_null"}},
        )
        cls = self.engine.entity_classes.get("Asset")
        assert cls is not None
        assert "value_check" in cls.validation_rules

    def test_define_entity_class_overwrites_existing(self):
        """Re-defining an entity class replaces the previous definition."""
        self.engine.define_entity_class("Item", properties={"color": {"type": "string"}})
        self.engine.define_entity_class("Item", properties={"size": {"type": "string"}})
        cls = self.engine.entity_classes.get("Item")
        assert "size" in cls.properties

    def test_define_entity_class_returns_entity_class(self):
        """define_entity_class returns the EntityClass instance."""
        result = self.engine.define_entity_class("Gadget", properties={})
        assert isinstance(result, EntityClass)
        assert result.name == "Gadget"

    # ------------------------------------------------------------------
    # Perspective creation
    # ------------------------------------------------------------------

    def test_create_perspective(self):
        """A perspective is registered in engine.perspectives."""
        self.engine.create_perspective(
            perspective_name="analyst_custom",
            entity_filters={"Person": ["name", "affiliation"]},
            role_based_view={"role_required": "analyst", "clearance_required": "internal"},
        )
        p = self.engine.perspectives.get("analyst_custom")
        assert p is not None
        assert p.name == "analyst_custom"
        assert p.role_required == "analyst"

    def test_create_multiple_perspectives(self):
        """Multiple perspectives can coexist in engine.perspectives."""
        self.engine.create_perspective(
            "view_a",
            entity_filters={},
            role_based_view={"role_required": "viewer"},
        )
        self.engine.create_perspective(
            "view_b",
            entity_filters={},
            role_based_view={"role_required": "admin"},
        )
        assert "view_a" in self.engine.perspectives
        assert "view_b" in self.engine.perspectives

    def test_create_perspective_clearance_stored(self):
        """Clearance level is stored on the perspective."""
        self.engine.create_perspective(
            "secret_view",
            entity_filters={},
            role_based_view={"role_required": "admin", "clearance_required": "secret"},
        )
        p = self.engine.perspectives.get("secret_view")
        assert p.clearance_required == "secret"

    # ------------------------------------------------------------------
    # Entity validation
    # ------------------------------------------------------------------

    def test_validate_entity_passes_when_valid(self):
        """A valid entity passes validation with no errors."""
        self.engine.define_entity_class(
            name="Location",
            properties={
                "lat": {"type": "number"},
                "lon": {"type": "number"},
                "id": {"type": "string", "required": True},
            },
        )
        result = self.engine.validate_entity(
            entity_data={"id": "loc-1", "lat": 51.5, "lon": -0.1},
            entity_class="Location",
        )
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_entity_fails_when_required_property_missing(self):
        """Missing a required property produces a validation error."""
        self.engine.define_entity_class(
            name="Contact",
            properties={
                "email": {"type": "string", "required": True},
            },
        )
        result = self.engine.validate_entity(
            entity_data={},
            entity_class="Contact",
        )
        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_entity_unknown_class(self):
        """Validating against an unregistered class returns invalid."""
        result = self.engine.validate_entity(
            entity_data={"field": "value"},
            entity_class="GhostClass",
        )
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_entity_not_null_rule(self):
        """A not_null validation rule fails when field is None."""
        self.engine.define_entity_class(
            name="Report",
            properties={"title": {"type": "string"}},
            validation_rules={"title_check": {"field": "title", "type": "not_null"}},
        )
        result = self.engine.validate_entity(
            entity_data={"title": None},
            entity_class="Report",
        )
        assert result.is_valid is False

    # ------------------------------------------------------------------
    # get_entity_class (via entity_classes dict)
    # ------------------------------------------------------------------

    def test_get_entity_class_missing_returns_none(self):
        """Looking up a non-existent class via entity_classes returns None."""
        assert self.engine.entity_classes.get("NonExistent") is None

    def test_get_entity_class_returns_entity_class_instance(self):
        """A registered class is accessible as an EntityClass instance."""
        self.engine.define_entity_class("Widget", properties={})
        cls = self.engine.entity_classes.get("Widget")
        assert isinstance(cls, EntityClass)

    # ------------------------------------------------------------------
    # Built-in entity types
    # ------------------------------------------------------------------

    def test_built_in_entity_types_registered(self):
        """Default entity types (Person, Organization, Event) are pre-registered."""
        for name in ("Person", "Organization", "Event"):
            cls = self.engine.entity_classes.get(name)
            assert cls is not None, f"Built-in class '{name}' should be registered"

    def test_built_in_location_registered(self):
        """Location is a built-in entity class."""
        assert self.engine.entity_classes.get("Location") is not None

    def test_built_in_asset_registered(self):
        """Asset is a built-in entity class."""
        assert self.engine.entity_classes.get("Asset") is not None

    def test_built_in_person_is_entity_class(self):
        """Person entity class is an EntityClass dataclass instance."""
        cls = self.engine.entity_classes.get("Person")
        assert isinstance(cls, EntityClass)

    def test_built_in_perspectives_registered(self):
        """Built-in perspectives (analyst_view, admin_view, viewer_view) exist."""
        for name in ("analyst_view", "admin_view", "viewer_view"):
            p = self.engine.perspectives.get(name)
            assert p is not None, f"Built-in perspective '{name}' should be registered"
