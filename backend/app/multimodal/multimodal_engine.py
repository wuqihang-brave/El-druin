"""Multi-modal data fusion engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

MODALITY_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "text": 1.0,
    "geospatial": 0.9,
    "image": 0.8,
    "audio": 0.7,
    "video": 0.75,
}


@dataclass
class ModalInput:
    """A single modal input to the fusion engine.

    Attributes:
        modality: text | image | audio | video | geospatial.
        data: Raw payload (bytes for media, str for text, dict for geo).
        metadata: Optional per-modal metadata.
    """

    modality: str
    data: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModalityResult:
    """Processed result from a single modality.

    Attributes:
        modality: Source modality.
        features: Extracted feature dict.
        text_representation: Canonical text for cross-modal fusion.
        confidence: Processing confidence [0.0, 1.0].
        metadata: Processing metadata.
    """

    modality: str
    features: dict[str, Any]
    text_representation: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossModalFeatures:
    """Cross-modal feature set after fusion.

    Attributes:
        unified_text: Merged text representation.
        feature_vector: Combined feature dict.
        modalities_used: Modalities that contributed.
        fusion_confidence: Overall fusion confidence.
    """

    unified_text: str
    feature_vector: dict[str, Any]
    modalities_used: list[str]
    fusion_confidence: float


@dataclass
class FusedResult:
    """Final fused result combining all modalities.

    Attributes:
        summary: Human-readable fused summary.
        features: Merged feature dict.
        confidence: Overall fusion confidence.
        modality_results: Per-modality results.
        unified_embedding: Combined embedding (if computed).
    """

    summary: str
    features: dict[str, Any]
    confidence: float
    modality_results: list[ModalityResult] = field(default_factory=list)
    unified_embedding: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class MultiModalEngine:
    """Multi-modal data fusion engine.

    Processes inputs from heterogeneous modalities and fuses them into a
    unified representation suitable for downstream intelligence analysis.

    Modality handlers dispatch to the specialised engines (geospatial,
    media processor) where available, with graceful fallback stubs.
    """

    async def process_multimodal(
        self, inputs: list[ModalInput]
    ) -> FusedResult:
        """Process a list of modal inputs and return a fused result.

        Args:
            inputs: List of :class:`ModalInput` instances.

        Returns:
            :class:`FusedResult` with combined analysis.
        """
        modality_results: list[ModalityResult] = []
        for modal_input in inputs:
            result = await self._process_single(modal_input)
            modality_results.append(result)

        return await self.fuse_modalities(modality_results)

    async def _process_single(self, modal_input: ModalInput) -> ModalityResult:
        """Dispatch a single modal input to the appropriate processor.

        Args:
            modal_input: Modal input to process.

        Returns:
            :class:`ModalityResult`.
        """
        modality = modal_input.modality.lower()

        if modality == "text":
            return ModalityResult(
                modality="text",
                features={"raw_text": modal_input.data[:500] if isinstance(modal_input.data, str) else ""},
                text_representation=str(modal_input.data)[:500],
                confidence=1.0,
            )

        if modality == "geospatial":
            return await self._process_geospatial(modal_input)

        if modality in ("image", "video", "audio"):
            return await self._process_media(modal_input)

        logger.warning("Unknown modality '%s'; treating as text", modality)
        return ModalityResult(
            modality=modality,
            features={"raw": str(modal_input.data)},
            text_representation=str(modal_input.data),
            confidence=0.5,
        )

    async def _process_geospatial(
        self, modal_input: ModalInput
    ) -> ModalityResult:
        """Process a geospatial input."""
        data = modal_input.data
        try:
            from app.multimodal.geospatial_engine import geospatial_engine

            if isinstance(data, str):
                coords = await geospatial_engine.geocode(data)
                text_repr = f"Location: {data} ({coords.lat}, {coords.lon})"
                features: dict = {"lat": coords.lat, "lon": coords.lon, "address": data}
            elif isinstance(data, dict):
                lat = data.get("lat", 0.0)
                lon = data.get("lon", 0.0)
                text_repr = f"Coordinates: ({lat}, {lon})"
                features = data
            else:
                text_repr = str(data)
                features = {"raw": str(data)}
        except Exception as exc:
            logger.warning("Geospatial processing failed: %s", exc)
            text_repr = str(data)
            features = {"raw": str(data)}

        return ModalityResult(
            modality="geospatial",
            features=features,
            text_representation=text_repr,
            confidence=0.9,
        )

    async def _process_media(self, modal_input: ModalInput) -> ModalityResult:
        """Process an image/video/audio input."""
        modality = modal_input.modality.lower()
        try:
            from app.multimodal.media_processor import media_processor

            if modality == "image" and isinstance(modal_input.data, bytes):
                analysis = await media_processor.process_image(modal_input.data)
                return ModalityResult(
                    modality="image",
                    features={"text_content": analysis.text_content, "objects": analysis.objects_detected},
                    text_representation=analysis.text_content or "Image processed.",
                    confidence=0.8,
                )
        except Exception as exc:
            logger.warning("Media processing failed: %s", exc)

        return ModalityResult(
            modality=modality,
            features={"size": len(modal_input.data) if isinstance(modal_input.data, bytes) else 0},
            text_representation=f"{modality.capitalize()} data received.",
            confidence=0.5,
        )

    async def fuse_modalities(
        self, modality_results: list[ModalityResult]
    ) -> FusedResult:
        """Fuse results from multiple modalities into a unified result.

        Confidence is computed as the weighted average of per-modality
        confidence values using :data:`MODALITY_CONFIDENCE_WEIGHTS`.

        Args:
            modality_results: Processed per-modality results.

        Returns:
            :class:`FusedResult`.
        """
        if not modality_results:
            return FusedResult(
                summary="No modal inputs provided.",
                features={},
                confidence=0.0,
            )

        # Merge features and text representations
        merged_features: dict = {}
        text_parts: list[str] = []
        total_weight = 0.0
        weighted_conf = 0.0

        for result in modality_results:
            merged_features.update(result.features)
            if result.text_representation:
                text_parts.append(result.text_representation)
            weight = MODALITY_CONFIDENCE_WEIGHTS.get(result.modality, 0.5)
            weighted_conf += result.confidence * weight
            total_weight += weight

        fusion_confidence = weighted_conf / total_weight if total_weight > 0 else 0.0
        unified_text = " | ".join(text_parts)

        # Optional: generate unified embedding
        unified_embedding: list[float] = []
        if unified_text:
            try:
                from app.core.embeddings import embedding_engine

                unified_embedding = await embedding_engine.encode(unified_text[:512])
            except Exception:
                pass

        return FusedResult(
            summary=unified_text[:1000],
            features=merged_features,
            confidence=round(fusion_confidence, 4),
            modality_results=modality_results,
            unified_embedding=unified_embedding,
        )

    async def extract_cross_modal_features(
        self, inputs: list[ModalInput]
    ) -> CrossModalFeatures:
        """Extract and unify features across all modalities.

        Args:
            inputs: List of :class:`ModalInput` instances.

        Returns:
            :class:`CrossModalFeatures` with unified representation.
        """
        fused = await self.process_multimodal(inputs)
        return CrossModalFeatures(
            unified_text=fused.summary,
            feature_vector=fused.features,
            modalities_used=[r.modality for r in fused.modality_results],
            fusion_confidence=fused.confidence,
        )


# Module-level singleton
multimodal_engine = MultiModalEngine()
