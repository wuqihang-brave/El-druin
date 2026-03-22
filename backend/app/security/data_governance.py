"""Data classification, retention, and compliance framework."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DataClassification:
    """Data classification result.

    Attributes:
        classification: Level (public | internal | confidential | secret).
        pii_detected: Whether PII fields were found.
        pii_fields: Names of fields that contain PII.
        caveats: Handling caveats (e.g. NOFORN).
        confidence: Classification confidence [0.0, 1.0].
    """

    classification: str
    pii_detected: bool = False
    pii_fields: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class RetentionDecision:
    """Data retention decision for an entity.

    Attributes:
        entity_id: Target entity.
        entity_type: Entity category.
        action: retain | archive | delete.
        reason: Human-readable justification.
        scheduled_at: Timestamp when the action should execute.
    """

    entity_id: str
    entity_type: str
    action: str  # retain | archive | delete
    reason: str
    scheduled_at: Optional[datetime] = None


@dataclass
class GDPRComplianceResult:
    """GDPR compliance check result.

    Attributes:
        is_compliant: Overall compliance flag.
        issues: List of compliance issues found.
        recommendations: Suggested remediation steps.
        data_subjects: Detected data subject identifiers.
    """

    is_compliant: bool
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    data_subjects: list[str] = field(default_factory=list)


@dataclass
class DataMap:
    """Tenant data map for GDPR article 30 record of processing.

    Attributes:
        tenant_id: Tenant this map belongs to.
        entity_types: List of entity types stored.
        pii_entity_types: Subset of types containing PII.
        total_records: Estimated total record count.
        retention_policies: Per-entity-type retention rules.
    """

    tenant_id: str
    entity_types: list[str] = field(default_factory=list)
    pii_entity_types: list[str] = field(default_factory=list)
    total_records: int = 0
    retention_policies: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_FIELD_NAMES: set[str] = {
    "email",
    "phone",
    "phone_number",
    "ssn",
    "social_security_number",
    "address",
    "street_address",
    "name",
    "full_name",
    "first_name",
    "last_name",
    "date_of_birth",
    "dob",
    "passport",
    "passport_number",
    "ip_address",
    "credit_card",
    "bank_account",
}

_PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "phone": re.compile(r"\b(?:\+?\d[\d\s\-()]{7,}\d)\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
}

# ---------------------------------------------------------------------------
# Retention policies (entity_type → days until action)
# ---------------------------------------------------------------------------

_RETENTION_POLICIES: dict[str, dict] = {
    "event": {"days": 365 * 3, "action": "archive"},
    "user": {"days": 365 * 7, "action": "archive"},
    "prediction": {"days": 365, "action": "archive"},
    "analysis": {"days": 365 * 2, "action": "archive"},
    "audit_log": {"days": 365 * 7, "action": "retain"},
}


# ---------------------------------------------------------------------------
# Framework
# ---------------------------------------------------------------------------


class DataGovernanceFramework:
    """Data classification, retention, and compliance framework.

    Attributes:
        _anonymization_salt: Salt used when pseudonymizing PII values.
    """

    def __init__(self) -> None:
        from app.config import settings
        self._anonymization_salt = settings.ANONYMIZATION_SALT

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify_data(
        self, data: dict[str, Any], context: dict[str, Any]
    ) -> DataClassification:
        """Classify a data record based on its fields and context.

        Args:
            data: Data record to classify.
            context: Additional context (source, purpose, tenant, etc.).

        Returns:
            :class:`DataClassification` result.
        """
        pii_fields: list[str] = []

        # Check field names
        for key in data:
            if key.lower() in _PII_FIELD_NAMES:
                pii_fields.append(key)

        # Check field values using regex patterns
        for key, value in data.items():
            if not isinstance(value, str):
                continue
            for pii_type, pattern in _PII_PATTERNS.items():
                if pattern.search(value) and key not in pii_fields:
                    pii_fields.append(key)
                    break

        pii_detected = len(pii_fields) > 0
        classification = "internal"
        if pii_detected:
            classification = "confidential"

        # Escalate based on context
        if context.get("classification"):
            context_class = context["classification"]
            levels = ["public", "internal", "confidential", "secret"]
            if levels.index(context_class) > levels.index(classification):
                classification = context_class

        caveats: list[str] = []
        if context.get("no_foreign_nationals"):
            caveats.append("NOFORN")

        return DataClassification(
            classification=classification,
            pii_detected=pii_detected,
            pii_fields=pii_fields,
            caveats=caveats,
        )

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def apply_retention_policy(
        self, entity_id: str, entity_type: str
    ) -> RetentionDecision:
        """Determine the retention action for an entity.

        Args:
            entity_id: Entity identifier.
            entity_type: Entity type string.

        Returns:
            :class:`RetentionDecision`.
        """
        policy = _RETENTION_POLICIES.get(
            entity_type.lower(), {"days": 365, "action": "archive"}
        )
        scheduled_at = datetime.now(UTC) + timedelta(days=policy["days"])
        return RetentionDecision(
            entity_id=entity_id,
            entity_type=entity_type,
            action=policy["action"],
            reason=f"Standard {entity_type} retention policy ({policy['days']} days)",
            scheduled_at=scheduled_at,
        )

    # ------------------------------------------------------------------
    # GDPR compliance
    # ------------------------------------------------------------------

    def check_gdpr_compliance(
        self, entity_data: dict[str, Any]
    ) -> GDPRComplianceResult:
        """Check a data record for GDPR compliance issues.

        Args:
            entity_data: Data record to check.

        Returns:
            :class:`GDPRComplianceResult`.
        """
        issues: list[str] = []
        recommendations: list[str] = []
        data_subjects: list[str] = []

        classification = self.classify_data(entity_data, {})
        if classification.pii_detected:
            for pii_field in classification.pii_fields:
                issues.append(
                    f"PII field '{pii_field}' requires lawful basis for processing"
                )
            recommendations.append(
                "Ensure a lawful basis (consent, contract, legitimate interest) is recorded"
            )
            recommendations.append(
                "Implement data minimisation — only collect strictly necessary fields"
            )

        if not entity_data.get("consent_recorded"):
            if classification.pii_detected:
                issues.append("No consent record found for PII data")

        if not entity_data.get("retention_policy"):
            recommendations.append(
                "Define a retention policy for this entity type"
            )

        email = entity_data.get("email", "")
        if email:
            data_subjects.append(email)

        return GDPRComplianceResult(
            is_compliant=len(issues) == 0,
            issues=issues,
            recommendations=recommendations,
            data_subjects=data_subjects,
        )

    # ------------------------------------------------------------------
    # Anonymization
    # ------------------------------------------------------------------

    def anonymize_pii(self, data: dict[str, Any]) -> dict[str, Any]:
        """Replace PII fields with pseudonymized values.

        Names and free-text PII fields are replaced with a deterministic
        pseudonym derived from the original value and a server-side salt,
        so re-identification without the salt is infeasible.

        Args:
            data: Data record containing PII.

        Returns:
            New dict with PII fields pseudonymized.
        """
        result = dict(data)
        classification = self.classify_data(data, {})

        for field_name in classification.pii_fields:
            original = str(result.get(field_name, ""))
            pseudonym = hashlib.sha256(
                f"{self._anonymization_salt}:{original}".encode()
            ).hexdigest()[:16]
            result[field_name] = f"ANON_{pseudonym}"

        return result

    # ------------------------------------------------------------------
    # Data map
    # ------------------------------------------------------------------

    async def generate_data_map(self, tenant_id: str) -> DataMap:
        """Build a GDPR article 30 data map for a tenant.

        Args:
            tenant_id: Tenant identifier.

        Returns:
            :class:`DataMap` populated with entity type statistics.
        """
        data_map = DataMap(tenant_id=tenant_id)
        try:
            from app.db.postgres import fetch_all, fetch_val

            tables = ["events", "predictions", "users", "analysis_results"]
            data_map.entity_types = tables
            data_map.pii_entity_types = ["users"]
            data_map.retention_policies = {
                etype: f"{_RETENTION_POLICIES.get(etype, {}).get('days', 365)} days"
                for etype in tables
            }
            for table in tables:
                count = await fetch_val(
                    f"SELECT COUNT(*) FROM {table} WHERE tenant_id = :tid",
                    {"tid": tenant_id},
                )
                data_map.total_records += count or 0
        except Exception as exc:
            logger.warning("Data map generation partial: %s", exc)
        return data_map


# Module-level singleton
data_governance = DataGovernanceFramework()
