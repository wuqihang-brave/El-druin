"""Async Pinecone vector-store client.

The official Pinecone SDK is synchronous; all calls are wrapped with
:func:`asyncio.to_thread` to avoid blocking the event loop.
"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from pinecone import Pinecone, ServerlessSpec  # type: ignore
    _PINECONE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PINECONE_AVAILABLE = False
    logger.warning("pinecone package not installed; vector search disabled")

from app.config import settings


class PineconeClient:
    """Async façade over the synchronous Pinecone SDK.

    Args:
        index_name: Name of the Pinecone index to use.

    Attributes:
        _index: Pinecone index object (lazy-initialized).
    """

    def __init__(self, index_name: Optional[str] = None) -> None:
        self._index_name = index_name or settings.PINECONE_INDEX_NAME
        self._index: Optional[Any] = None
        self._pc: Optional[Any] = None

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init(self) -> None:
        """Lazily initialize the Pinecone client and index."""
        if self._index is not None:
            return
        if not _PINECONE_AVAILABLE:
            raise RuntimeError("pinecone library is not installed")
        if not settings.PINECONE_API_KEY:
            raise RuntimeError("PINECONE_API_KEY is not configured")

        self._pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        existing = [i.name for i in self._pc.list_indexes()]
        if self._index_name not in existing:
            self._pc.create_index(
                name=self._index_name,
                dimension=settings.EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            logger.info("Created Pinecone index '%s'", self._index_name)
        self._index = self._pc.Index(self._index_name)

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def upsert_vectors(
        self,
        vectors: list[dict[str, Any]],
        namespace: str = "",
    ) -> dict:
        """Upsert vectors into the index.

        Args:
            vectors: List of dicts with ``id``, ``values``, and optional
                ``metadata`` keys.
            namespace: Pinecone namespace to upsert into.

        Returns:
            Upsert response dict.
        """
        self._init()
        return await asyncio.to_thread(
            self._index.upsert,
            vectors=vectors,
            namespace=namespace,
        )

    async def upsert_batch(
        self,
        vectors: list[dict[str, Any]],
        batch_size: int = 100,
        namespace: str = "",
    ) -> list[dict]:
        """Upsert vectors in batches to respect API limits.

        Args:
            vectors: Full list of vectors to upsert.
            batch_size: Number of vectors per request.
            namespace: Pinecone namespace.

        Returns:
            List of upsert response dicts (one per batch).
        """
        responses: list[dict] = []
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            response = await self.upsert_vectors(batch, namespace=namespace)
            responses.append(response)
        return responses

    async def query_similar(
        self,
        vector: list[float],
        top_k: int = 10,
        namespace: str = "",
        filter: Optional[dict] = None,
        include_metadata: bool = True,
    ) -> list[dict]:
        """Find the most similar vectors in the index.

        Args:
            vector: Query embedding.
            top_k: Number of nearest neighbours to return.
            namespace: Pinecone namespace to search.
            filter: Optional metadata filter dict.
            include_metadata: Whether to include stored metadata.

        Returns:
            List of match dicts (``id``, ``score``, ``metadata``).
        """
        self._init()
        kwargs: dict[str, Any] = {
            "vector": vector,
            "top_k": top_k,
            "namespace": namespace,
            "include_metadata": include_metadata,
        }
        if filter:
            kwargs["filter"] = filter

        result = await asyncio.to_thread(self._index.query, **kwargs)
        return [
            {
                "id": m["id"],
                "score": m["score"],
                "metadata": m.get("metadata", {}),
            }
            for m in result.get("matches", [])
        ]

    async def delete_vectors(
        self,
        ids: list[str],
        namespace: str = "",
    ) -> dict:
        """Delete vectors by ID.

        Args:
            ids: List of vector IDs to delete.
            namespace: Pinecone namespace.

        Returns:
            Delete response dict.
        """
        self._init()
        return await asyncio.to_thread(
            self._index.delete,
            ids=ids,
            namespace=namespace,
        )

    async def fetch_vectors(
        self,
        ids: list[str],
        namespace: str = "",
    ) -> dict[str, Any]:
        """Fetch vectors by ID.

        Args:
            ids: List of vector IDs to fetch.
            namespace: Pinecone namespace.

        Returns:
            Dict mapping vector ID → vector data.
        """
        self._init()
        result = await asyncio.to_thread(
            self._index.fetch,
            ids=ids,
            namespace=namespace,
        )
        return result.get("vectors", {})

    async def describe_index(self) -> dict:
        """Return index statistics.

        Returns:
            Index stats dict.
        """
        self._init()
        result = await asyncio.to_thread(self._index.describe_index_stats)
        return dict(result)


# Module-level singleton
pinecone_client = PineconeClient()
