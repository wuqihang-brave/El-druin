"""Text embedding engine backed by sentence-transformers.

The model is loaded lazily on first use to avoid slowing startup when
the embedding capability is not needed.
"""

import asyncio
import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _ST_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ST_AVAILABLE = False
    logger.warning("sentence-transformers not installed; embeddings disabled")

from app.config import settings


class EmbeddingEngine:
    """Async embedding engine wrapping sentence-transformers.

    The model is loaded once and reused for subsequent requests.  All
    inference calls are offloaded to a thread pool so as not to block
    the asyncio event loop.

    Attributes:
        _model_name: Sentence-transformer model identifier.
        _model: Loaded :class:`SentenceTransformer` instance (lazy).
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self._model_name = model_name or settings.EMBEDDING_MODEL
        self._model: Optional[Any] = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    async def _get_model(self) -> Any:
        """Return the loaded model, initialising it on first call."""
        async with self._lock:
            if self._model is None:
                if not _ST_AVAILABLE:
                    raise RuntimeError(
                        "sentence-transformers is not installed"
                    )
                self._model = await asyncio.to_thread(
                    SentenceTransformer, self._model_name
                )
                logger.info(
                    "Loaded embedding model '%s'", self._model_name
                )
        return self._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def encode(self, text: str) -> list[float]:
        """Encode a single text into a dense embedding vector.

        Args:
            text: Input text.

        Returns:
            Float list of length :attr:`settings.EMBEDDING_DIMENSION`.
        """
        # Try Redis cache first
        try:
            from app.db.redis_client import redis_client
            cache_key = f"emb:{hash(text)}"
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

        model = await self._get_model()
        vector: list[float] = await asyncio.to_thread(
            lambda: model.encode(text, convert_to_numpy=True).tolist()
        )

        try:
            from app.db.redis_client import redis_client
            await redis_client.set(f"emb:{hash(text)}", vector, ttl=3600)
        except Exception:
            pass

        return vector

    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts in a single batched call.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors in the same order as *texts*.
        """
        model = await self._get_model()
        vectors: list[list[float]] = await asyncio.to_thread(
            lambda: model.encode(texts, convert_to_numpy=True).tolist()
        )
        return vectors

    async def encode_event(self, event: dict) -> list[float]:
        """Build a composite embedding from event fields.

        Combines ``title``, ``description``, and ``tags`` into a single
        text and encodes it.

        Args:
            event: Event dict with optional ``title``, ``description``,
                and ``tags`` keys.

        Returns:
            Embedding vector for the event.
        """
        parts: list[str] = []
        if event.get("title"):
            parts.append(event["title"])
        if event.get("description"):
            parts.append(event["description"])
        tags = event.get("tags", [])
        if tags:
            parts.append(" ".join(tags))
        text = " ".join(parts) or "unknown event"
        return await self.encode(text)

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First embedding vector.
            b: Second embedding vector.

        Returns:
            Cosine similarity in [-1.0, 1.0].
        """
        if len(a) != len(b):
            raise ValueError("Vectors must be the same length")
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# Module-level singleton
embedding_engine = EmbeddingEngine()
