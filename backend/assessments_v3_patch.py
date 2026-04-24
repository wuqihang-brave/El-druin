"""
assessments_v3_patch.py
=======================
Shim that re-exports the three patch helpers from app.services.assessment_patch
so that assessment_generator.py (which does `from assessments_v3_patch import ...`)
and assessments.py can both import them by the same short name from the backend/ root.
"""
from app.services.assessment_patch import (  # noqa: F401
    build_evidence_items,
    derive_active_pairs_from_assessment,
    build_enriched_velocity_data,
)
