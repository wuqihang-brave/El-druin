"""MiroFish predictive analytics integration adapter."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import aiohttp  # type: ignore
    _AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AIOHTTP_AVAILABLE = False

from app.config import settings


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

_PREDICTION_MAP: dict[str, str] = {
    "entityId": "entity_id",
    "predictionType": "prediction_type",
    "score": "confidence",
    "horizon": "timeframe",
    "details": "analysis",
    "createdAt": "created_at",
}

_RISK_MAP: dict[str, str] = {
    "overall": "overall_risk",
    "financial": "financial_risk",
    "reputational": "reputational_risk",
    "operational": "operational_risk",
    "geopolitical": "geopolitical_risk",
}


class MiroFishAdapter:
    """MiroFish predictive analytics integration.

    Fetches predictions, risk scores, and network analysis from the
    MiroFish API and normalises them for use within EL'druin.

    Args:
        endpoint: MiroFish API base URL.
        api_key: MiroFish API key.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._endpoint = (
            endpoint
            or getattr(settings, "MIROFISH_ENDPOINT", "https://api.mirofish.example.com/v2")
        )
        self._api_key = (
            api_key or getattr(settings, "MIROFISH_API_KEY", "")
        )
        self._session: Optional[Any] = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> Any:
        """Return a lazily-created aiohttp session."""
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required for MiroFish adapter")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-API-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Make an authenticated request to the MiroFish API.

        Args:
            method: HTTP method.
            path: API path.
            **kwargs: Extra kwargs for aiohttp.

        Returns:
            Parsed JSON response.
        """
        import asyncio

        url = f"{self._endpoint.rstrip('/')}/{path.lstrip('/')}"
        session = await self._get_session()
        last_exc: Optional[Exception] = None

        for attempt in range(1, 4):
            try:
                async with session.request(method, url, **kwargs) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "MiroFish request attempt %d failed: %s", attempt, exc
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError("MiroFish request failed after 3 attempts") from last_exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_predictions(
        self, entity_ids: list[str], timeframe: str = "30d"
    ) -> list[dict]:
        """Fetch predictions for a list of entities.

        Args:
            entity_ids: List of entity identifiers.
            timeframe: Prediction horizon string (e.g. "30d", "90d").

        Returns:
            List of normalised prediction dicts.
        """
        try:
            data = await self._request(
                "POST",
                "/predictions",
                json={"entity_ids": entity_ids, "timeframe": timeframe},
            )
            raw: list[dict] = data.get("predictions", data) if isinstance(data, dict) else data
            return [self.normalize_prediction(p) for p in raw]
        except Exception as exc:
            logger.error("MiroFish get_predictions failed: %s", exc)
            return []

    async def get_risk_scores(self, entity_id: str) -> dict:
        """Fetch risk scores for a single entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            Normalised risk score dict.
        """
        try:
            data = await self._request("GET", f"/risk/{entity_id}")
            return self._normalize_risk(data if isinstance(data, dict) else {})
        except Exception as exc:
            logger.error("MiroFish get_risk_scores for %s failed: %s", entity_id, exc)
            return {}

    async def get_network_analysis(self, entity_ids: list[str]) -> dict:
        """Fetch network / relationship analysis for a set of entities.

        Args:
            entity_ids: List of entity identifiers.

        Returns:
            Network analysis result dict.
        """
        try:
            data = await self._request(
                "POST",
                "/network",
                json={"entity_ids": entity_ids},
            )
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.error("MiroFish get_network_analysis failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def normalize_prediction(self, raw_prediction: dict) -> dict:
        """Map a MiroFish prediction dict to the internal format.

        Args:
            raw_prediction: Raw MiroFish prediction dict.

        Returns:
            Normalised prediction dict.
        """
        normalised: dict = {}
        for mf_field, internal_field in _PREDICTION_MAP.items():
            if mf_field in raw_prediction:
                normalised[internal_field] = raw_prediction[mf_field]

        # Ensure confidence is in [0.0, 1.0]
        conf = normalised.get("confidence", 0.5)
        if isinstance(conf, (int, float)) and conf > 1.0:
            conf = conf / 100.0  # MiroFish may return percentages
        normalised["confidence"] = max(0.0, min(1.0, float(conf)))

        normalised["source"] = "mirofish"
        extra = {k: v for k, v in raw_prediction.items() if k not in _PREDICTION_MAP}
        normalised.setdefault("metadata", {}).update(extra)
        return normalised

    def _normalize_risk(self, raw: dict) -> dict:
        """Map MiroFish risk fields to internal names.

        Args:
            raw: Raw risk score dict.

        Returns:
            Normalised risk dict.
        """
        result: dict = {}
        for mf_field, internal_field in _RISK_MAP.items():
            if mf_field in raw:
                result[internal_field] = raw[mf_field]
        result.setdefault("source", "mirofish")
        return result


# Module-level singleton
mirofish_adapter = MiroFishAdapter()
