"""Attribute-Based Access Control (ABAC) engine with multi-tenancy support."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

CLEARANCE_LEVELS: list[str] = ["public", "internal", "confidential", "secret"]


@dataclass
class UserPermissions:
    """Effective permissions for a user.

    Attributes:
        user_id: User identifier.
        roles: List of assigned roles.
        clearance_level: Effective data clearance.
        tenant_id: Tenant isolation scope.
        allowed_actions: Explicit action allow-list.
        denied_resources: Explicit resource deny-list.
    """

    user_id: str
    roles: list[str] = field(default_factory=list)
    clearance_level: str = "internal"
    tenant_id: str = "default"
    allowed_actions: list[str] = field(default_factory=list)
    denied_resources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AccessControlEngine:
    """ABAC engine with row/column-level security and multi-tenancy.

    Evaluates policies based on user attributes (roles, clearance level,
    tenant) and resource attributes (classification, tenant, owner).

    Attributes:
        _classifications: In-memory classification registry.
        _policies: Registered policy dicts.
    """

    # Clearance comparison index: higher index → higher clearance
    _CLEARANCE_INDEX: dict[str, int] = {
        level: idx for idx, level in enumerate(CLEARANCE_LEVELS)
    }

    # Default role-to-action permissions
    _ROLE_ACTIONS: dict[str, list[str]] = {
        "viewer": ["read"],
        "analyst": ["read", "create", "export"],
        "admin": ["read", "create", "update", "delete", "export", "admin"],
    }

    def __init__(self) -> None:
        self._classifications: dict[str, dict] = {}
        self._policies: list[dict] = []

    # ------------------------------------------------------------------
    # Core access check
    # ------------------------------------------------------------------

    def check_access(
        self,
        user_id: str,
        user_attrs: dict[str, Any],
        resource_id: str,
        resource_attrs: dict[str, Any],
        action: str,
    ) -> bool:
        """Evaluate whether a user may perform an action on a resource.

        Args:
            user_id: Requesting user's ID.
            user_attrs: User attribute dict (roles, clearance, tenant_id).
            resource_id: Target resource identifier.
            resource_attrs: Resource attribute dict (classification, tenant_id).
            action: Requested action string (read, write, delete, …).

        Returns:
            True if access is granted, False otherwise.
        """
        # Tenant isolation
        user_tenant = user_attrs.get("tenant_id", "default")
        resource_tenant = resource_attrs.get("tenant_id", "default")
        if user_tenant != resource_tenant and "admin" not in user_attrs.get(
            "roles", []
        ):
            logger.debug(
                "Access denied: tenant mismatch user=%s resource=%s",
                user_tenant,
                resource_tenant,
            )
            return False

        # Clearance check
        user_clearance = user_attrs.get("clearance_level", "public")
        resource_classification = resource_attrs.get(
            "classification", "internal"
        )
        if not self._has_sufficient_clearance(
            user_clearance, resource_classification
        ):
            logger.debug(
                "Access denied: clearance too low user=%s resource=%s",
                user_clearance,
                resource_classification,
            )
            return False

        # Role-based action check
        roles: list[str] = user_attrs.get("roles", ["viewer"])
        allowed_actions: list[str] = []
        for role in roles:
            allowed_actions.extend(self._ROLE_ACTIONS.get(role, []))

        if action not in allowed_actions:
            logger.debug(
                "Access denied: action '%s' not in %s",
                action,
                allowed_actions,
            )
            return False

        # Evaluate registered policies
        for policy in self._policies:
            result = self.evaluate_policy(policy, user_attrs, resource_attrs)
            if not result:
                return False

        return True

    # ------------------------------------------------------------------
    # Classification management
    # ------------------------------------------------------------------

    def set_data_classification(
        self,
        entity_id: str,
        classification: str,
        caveats: Optional[list[str]] = None,
    ) -> bool:
        """Assign a data classification to an entity.

        Args:
            entity_id: Entity to classify.
            classification: Classification level.
            caveats: Optional caveat strings (e.g. "NOFORN").

        Returns:
            True if stored successfully.
        """
        self._classifications[entity_id] = {
            "classification": classification,
            "caveats": caveats or [],
        }
        return True

    # ------------------------------------------------------------------
    # Row / Column filtering
    # ------------------------------------------------------------------

    def filter_rows(
        self,
        query_result: list[dict],
        user_attributes: dict[str, Any],
    ) -> list[dict]:
        """Filter a list of records to those the user may access.

        Args:
            query_result: List of record dicts.
            user_attributes: Requesting user's attribute dict.

        Returns:
            Subset of records the user can access.
        """
        visible: list[dict] = []
        for record in query_result:
            record_attrs = {
                "classification": record.get("classification", "internal"),
                "tenant_id": record.get("tenant_id", "default"),
            }
            if self.check_access(
                user_attributes.get("user_id", ""),
                user_attributes,
                record.get("id", ""),
                record_attrs,
                "read",
            ):
                visible.append(record)
        return visible

    def filter_columns(
        self,
        record: dict,
        user_clearance: str,
    ) -> dict:
        """Remove fields whose classification exceeds the user's clearance.

        Args:
            record: Record dict with optional ``_field_classifications`` key.
            user_clearance: User's clearance level.

        Returns:
            Record dict with over-classified fields removed.
        """
        field_classifications: dict[str, str] = record.pop(
            "_field_classifications", {}
        )
        if not field_classifications:
            return record

        filtered: dict = {}
        for key, value in record.items():
            field_class = field_classifications.get(key, "public")
            if self._has_sufficient_clearance(user_clearance, field_class):
                filtered[key] = value
        return filtered

    # ------------------------------------------------------------------
    # Tenant isolation
    # ------------------------------------------------------------------

    def isolate_tenant_data(self, tenant_id: str, query: str) -> str:
        """Inject a tenant isolation filter into a raw SQL query.

        Args:
            tenant_id: Tenant identifier.
            query: Original SQL query string.

        Returns:
            Modified SQL query with tenant filter appended.

        Note:
            This is a simple string-based approach for illustration.
            Production use should use parameterised queries via SQLAlchemy.
        """
        if "WHERE" in query.upper():
            return f"{query} AND tenant_id = '{tenant_id}'"
        return f"{query} WHERE tenant_id = '{tenant_id}'"

    # ------------------------------------------------------------------
    # Policy evaluation
    # ------------------------------------------------------------------

    def evaluate_policy(
        self,
        policy: dict[str, Any],
        user_attrs: dict[str, Any],
        resource_attrs: dict[str, Any],
    ) -> bool:
        """Evaluate a single policy dict.

        Supports ``allow`` and ``deny`` policy types with simple
        attribute-equality conditions.

        Args:
            policy: Policy definition dict.
            user_attrs: User attribute dict.
            resource_attrs: Resource attribute dict.

        Returns:
            True if the policy allows the access, False if it denies.
        """
        policy_type = policy.get("type", "allow")
        conditions: list[dict] = policy.get("conditions", [])

        for condition in conditions:
            attr_source = condition.get("source", "user")
            attr_name = condition.get("attribute", "")
            expected = condition.get("value")

            attrs = user_attrs if attr_source == "user" else resource_attrs
            actual = attrs.get(attr_name)

            operator = condition.get("operator", "eq")
            if operator == "eq" and actual != expected:
                # Condition not met — policy doesn't apply
                return True if policy_type == "allow" else True
            if operator == "ne" and actual == expected:
                return True if policy_type == "allow" else True

        # All conditions met
        return policy_type == "allow"

    # ------------------------------------------------------------------
    # User permissions
    # ------------------------------------------------------------------

    async def get_user_permissions(self, user_id: str) -> UserPermissions:
        """Build effective permissions for a user by querying the database.

        Args:
            user_id: User identifier.

        Returns:
            :class:`UserPermissions` for the user.
        """
        try:
            from app.db.postgres import fetch_one

            row = await fetch_one(
                "SELECT roles, clearance_level, tenant_id "
                "FROM users WHERE id = :user_id",
                {"user_id": user_id},
            )
            if row:
                roles: list[str] = row.get("roles") or ["viewer"]
                clearance = row.get("clearance_level", "internal")
                tenant = row.get("tenant_id", "default")
                allowed: list[str] = []
                for role in roles:
                    allowed.extend(self._ROLE_ACTIONS.get(role, []))
                return UserPermissions(
                    user_id=user_id,
                    roles=roles,
                    clearance_level=clearance,
                    tenant_id=tenant,
                    allowed_actions=list(set(allowed)),
                )
        except Exception as exc:
            logger.warning("Failed to load permissions for %s: %s", user_id, exc)

        return UserPermissions(user_id=user_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _has_sufficient_clearance(
        self, user_clearance: str, resource_classification: str
    ) -> bool:
        """Check if user clearance meets or exceeds resource classification.

        Args:
            user_clearance: User's clearance level string.
            resource_classification: Resource's classification string.

        Returns:
            True if user has sufficient clearance.
        """
        user_idx = self._CLEARANCE_INDEX.get(user_clearance, 0)
        resource_idx = self._CLEARANCE_INDEX.get(resource_classification, 1)
        return user_idx >= resource_idx


# Module-level singleton
access_control = AccessControlEngine()
