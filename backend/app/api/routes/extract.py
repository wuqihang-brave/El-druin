"""
Extraction + Human Feedback API routes.

Endpoints:
  POST /extract/extract-with-interpretation  – extract entities/relations + philosophical interpretation
  POST /extract/save-human-feedback          – persist human accept/reject feedback (RLHF data)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/extract", tags=["extraction"])

# Path relative to the repo root; resolved at call time so it works whether the
# backend is started from the repo root or the backend/ sub-directory.
_FEEDBACK_FILE_RELATIVE = Path("data/human_preference_alignment.jsonl")


def _resolve_feedback_file() -> Path:
    """Resolve the JSONL feedback file path relative to the project root."""
    # Walk up from this file's location to find the repo root (contains 'backend/')
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "backend").is_dir() and (parent / "frontend").is_dir():
            return parent / _FEEDBACK_FILE_RELATIVE
    # Fallback: use cwd
    return Path.cwd() / _FEEDBACK_FILE_RELATIVE


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ExtractionRequest(BaseModel):
    news_text: str = Field(..., min_length=1, max_length=20000, description="News article text")
    news_title: str = Field("", max_length=500, description="News article title (optional)")


class RelationFeedback(BaseModel):
    relation_id: str = Field(..., description="Unique identifier for the relation (e.g. 'rel_0')")
    from_entity: str = Field(..., description="Source entity name")
    to_entity: str = Field(..., description="Target entity name")
    relation_type: str = Field(..., description="Relation type / label")
    action: str = Field(..., pattern="^(accept|reject)$", description="'accept' or 'reject'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Relation confidence score")
    reason: Optional[str] = Field(None, description="Optional reason for rejection")


class HumanFeedbackRequest(BaseModel):
    news_id: str = Field(..., description="Unique identifier for the news article (SHA-256 prefix)")
    feedback_list: List[RelationFeedback] = Field(..., description="List of per-relation feedback items")
    user_id: str = Field("wuqihang-brave", description="User identifier")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/extract-with-interpretation")
def extract_with_interpretation(req: ExtractionRequest) -> Dict[str, Any]:
    """Extract entities/relations from news text and generate a philosophical interpretation.

    Steps:
    1. Call EntityRelationExtractor to obtain entities and relations.
    2. Call OrderCritic.generate_philosophical_interpretation() for a 2-3 sentence
       philosophical commentary on the extracted knowledge.
    3. Return all results (used by the frontend to display the feedback UI).
    """
    from app.knowledge.entity_extractor import EntityRelationExtractor
    from knowledge_layer.order_critic import OrderCritic

    # Generate a stable news ID (first 16 hex chars of SHA-256)
    news_id = hashlib.sha256(
        f"{req.news_title}:{req.news_text}".encode("utf-8")
    ).hexdigest()[:16]

    # Entity/relation extraction
    try:
        extraction_result = EntityRelationExtractor().extract(req.news_text)
    except Exception as exc:
        logger.error("Extraction failed: %s", exc)
        extraction_result = {"entities": [], "relations": []}

    entities: List[Dict[str, Any]] = extraction_result.get("entities", [])
    relations: List[Dict[str, Any]] = extraction_result.get("relations", [])

    # Assign stable IDs to each relation for client-side tracking
    for idx, rel in enumerate(relations):
        rel.setdefault("id", f"rel_{idx}")

    # Philosophical interpretation
    try:
        order_critic = OrderCritic()
        interpretation = order_critic.generate_philosophical_interpretation(
            entities=entities,
            relations=relations,
            original_news=req.news_text,
            news_title=req.news_title,
        )
    except Exception as exc:
        logger.error("Philosophical interpretation failed: %s", exc)
        interpretation = ""

    return {
        "news_id": news_id,
        "news_title": req.news_title,
        "entities": entities,
        "relations": relations,
        "philosophical_interpretation": interpretation,
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/save-human-feedback")
def save_human_feedback(req: HumanFeedbackRequest) -> Dict[str, Any]:
    """Persist human accept/reject feedback to a JSONL file for future RLHF training.

    Each call appends one JSON record to ``data/human_preference_alignment.jsonl``.
    """
    feedback_file = _resolve_feedback_file()
    feedback_file.parent.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()

    feedback_record: Dict[str, Any] = {
        "news_id": req.news_id,
        "feedback_timestamp": now_iso,
        "human_feedback": [
            {
                "relation_id": f.relation_id,
                "from": f.from_entity,
                "to": f.to_entity,
                "relation_type": f.relation_type,
                "action": f.action,
                "confidence": f.confidence,
                "user_id": req.user_id,
                "feedback_timestamp": now_iso,
                "reason": f.reason,
            }
            for f in req.feedback_list
        ],
        "model_version": "v1.0",
    }

    try:
        with open(feedback_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(feedback_record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.error("Failed to write feedback file %s: %s", feedback_file, exc)
        return {"status": "error", "message": str(exc)}

    logger.info(
        "Saved %d feedback items for news_id=%s to %s",
        len(req.feedback_list),
        req.news_id,
        feedback_file,
    )
    return {
        "status": "success",
        "feedback_count": len(req.feedback_list),
        "saved_to": str(feedback_file),
    }
