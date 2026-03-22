"""Unit tests for AccessControlEngine."""

from __future__ import annotations

import pytest
from app.security.access_control_engine import AccessControlEngine


class TestAccessControlEngine:
    """Tests for the ABAC access control engine."""

    def setup_method(self):
        self.acl = AccessControlEngine()

    # ------------------------------------------------------------------
    # Basic clearance / role checks
    # ------------------------------------------------------------------

    def test_admin_can_access_secret(self):
        """Admin user with top-level clearance can read secret-classified resources."""
        granted = self.acl.check_access(
            user_id="admin-1",
            user_attrs={"roles": ["admin"], "clearance_level": "secret", "tenant_id": "org"},
            resource_id="doc-secret",
            resource_attrs={"classification": "secret", "tenant_id": "org"},
            action="read",
        )
        assert granted is True

    def test_viewer_can_access_public(self):
        """Viewer role with public clearance can read public resources."""
        granted = self.acl.check_access(
            user_id="viewer-1",
            user_attrs={"roles": ["viewer"], "clearance_level": "public", "tenant_id": "org"},
            resource_id="doc-public",
            resource_attrs={"classification": "public", "tenant_id": "org"},
            action="read",
        )
        assert granted is True

    def test_user_cannot_access_classified(self):
        """A viewer with internal clearance cannot access confidential resources."""
        granted = self.acl.check_access(
            user_id="user-1",
            user_attrs={"roles": ["viewer"], "clearance_level": "internal", "tenant_id": "org"},
            resource_id="doc-conf",
            resource_attrs={"classification": "confidential", "tenant_id": "org"},
            action="read",
        )
        assert granted is False

    def test_viewer_cannot_delete(self):
        """Viewer role does not have delete permission."""
        granted = self.acl.check_access(
            user_id="viewer-1",
            user_attrs={"roles": ["viewer"], "clearance_level": "internal", "tenant_id": "org"},
            resource_id="doc-1",
            resource_attrs={"classification": "internal", "tenant_id": "org"},
            action="delete",
        )
        assert granted is False

    def test_analyst_can_export(self):
        """Analyst role includes the 'export' action."""
        granted = self.acl.check_access(
            user_id="analyst-1",
            user_attrs={"roles": ["analyst"], "clearance_level": "confidential", "tenant_id": "org"},
            resource_id="report-1",
            resource_attrs={"classification": "internal", "tenant_id": "org"},
            action="export",
        )
        assert granted is True

    # ------------------------------------------------------------------
    # Data classification
    # ------------------------------------------------------------------

    def test_data_classification_stored(self):
        """set_data_classification returns True and stores the entry."""
        result = self.acl.set_data_classification(
            entity_id="entity-123",
            classification="confidential",
            caveats=["NOFORN"],
        )
        assert result is True
        stored = self.acl._classifications.get("entity-123")
        assert stored is not None
        assert stored["classification"] == "confidential"
        assert "NOFORN" in stored["caveats"]

    def test_data_classification_without_caveats(self):
        """Classification without caveats defaults to empty list."""
        self.acl.set_data_classification("entity-456", "internal")
        stored = self.acl._classifications["entity-456"]
        assert stored["caveats"] == []

    # ------------------------------------------------------------------
    # Column filtering
    # ------------------------------------------------------------------

    def test_column_filtering_removes_high_clearance_fields(self):
        """filter_columns strips fields whose classification exceeds user clearance."""
        record = {
            "name": "Alice",
            "ssn": "123-45-6789",
            "_field_classifications": {
                "name": "public",
                "ssn": "secret",
            },
        }
        filtered = self.acl.filter_columns(record, user_clearance="internal")
        assert "name" in filtered
        assert "ssn" not in filtered

    def test_column_filtering_passes_all_when_high_clearance(self):
        """filter_columns keeps all fields when user has sufficient clearance."""
        record = {
            "name": "Bob",
            "salary": 120000,
            "_field_classifications": {
                "name": "public",
                "salary": "confidential",
            },
        }
        filtered = self.acl.filter_columns(record, user_clearance="confidential")
        assert "name" in filtered
        assert "salary" in filtered

    def test_column_filtering_noop_without_field_classifications(self):
        """filter_columns returns record unchanged when no _field_classifications key."""
        record = {"foo": "bar", "baz": 42}
        filtered = self.acl.filter_columns(record.copy(), user_clearance="public")
        assert filtered == {"foo": "bar", "baz": 42}

    # ------------------------------------------------------------------
    # Tenant isolation
    # ------------------------------------------------------------------

    def test_tenant_isolation_denies_cross_tenant(self):
        """Users cannot access resources belonging to a different tenant."""
        granted = self.acl.check_access(
            user_id="user-tenant-a",
            user_attrs={"roles": ["analyst"], "clearance_level": "secret", "tenant_id": "tenant-a"},
            resource_id="doc-tenant-b",
            resource_attrs={"classification": "public", "tenant_id": "tenant-b"},
            action="read",
        )
        assert granted is False

    def test_admin_bypasses_tenant_isolation(self):
        """Admin role can access resources from any tenant."""
        granted = self.acl.check_access(
            user_id="super-admin",
            user_attrs={"roles": ["admin"], "clearance_level": "secret", "tenant_id": "tenant-a"},
            resource_id="doc-tenant-b",
            resource_attrs={"classification": "public", "tenant_id": "tenant-b"},
            action="read",
        )
        assert granted is True

    # ------------------------------------------------------------------
    # Row filtering
    # ------------------------------------------------------------------

    def test_filter_rows_excludes_inaccessible_records(self):
        """filter_rows only returns records the user can access."""
        records = [
            {"id": "r1", "classification": "public", "tenant_id": "org"},
            {"id": "r2", "classification": "secret", "tenant_id": "org"},
        ]
        visible = self.acl.filter_rows(
            records,
            user_attributes={"user_id": "u1", "roles": ["viewer"], "clearance_level": "public", "tenant_id": "org"},
        )
        ids = [r["id"] for r in visible]
        assert "r1" in ids
        assert "r2" not in ids
