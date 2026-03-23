"""
Caching layer for the EL'druin knowledge-graph extractor.

Provides a module-level :func:`cached_extract` wrapper that uses
:func:`functools.lru_cache` to avoid redundant LLM calls for identical
input texts.

The cache is keyed on the **normalised** text (stripped, lower-cased) so
that cosmetically different but semantically identical inputs share a cached
result.

Usage::

    from kg.cache import cached_extract

    triples = cached_extract("Apple CEO Tim Cook met EU regulators.")
    triples_again = cached_extract("Apple CEO Tim Cook met EU regulators.")
    # Second call returns instantly from cache.

Cache statistics are available via :func:`cache_info`::

    from kg.cache import cache_info, clear_cache
    print(cache_info())   # CacheInfo(hits=1, misses=1, ...)
    clear_cache()         # reset the cache
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Tuple

from kg.models import Triple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton extractor – created on first use so the module can be
# imported without triggering LLM initialisation.
# ---------------------------------------------------------------------------

_extractor_singleton = None


def _get_extractor():
    global _extractor_singleton  # noqa: PLW0603
    if _extractor_singleton is None:
        from kg.llm_extractor import KGExtractor  # local import avoids circular deps

        _extractor_singleton = KGExtractor()
    return _extractor_singleton


# ---------------------------------------------------------------------------
# Internal cached helper
# ---------------------------------------------------------------------------

@lru_cache(maxsize=512)
def _cached_extract_impl(normalised_text: str) -> Tuple[Triple, ...]:
    """Cached core that operates on a *tuple* return so lru_cache works.

    ``lru_cache`` requires hashable arguments and a hashable return value.
    We use a ``tuple`` of :class:`~kg.models.Triple` objects as the cached
    result and expose a ``List`` via the public wrapper.
    """
    extractor = _get_extractor()
    triples = extractor.extract(normalised_text)
    logger.debug(
        "Cache miss for text (len=%d): extracted %d triples",
        len(normalised_text),
        len(triples),
    )
    return tuple(triples)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cached_extract(text: str) -> List[Triple]:
    """Extract triples from *text*, using the LRU cache.

    Identical texts (after normalisation) return cached results without
    calling the LLM again.

    Args:
        text: Raw news text.

    Returns:
        List of :class:`~kg.models.Triple` objects.
    """
    if not text or not text.strip():
        return []

    # Normalise: strip whitespace and lower-case for cache key stability.
    normalised = text.strip().lower()
    return list(_cached_extract_impl(normalised))


def cache_info():
    """Return the underlying ``lru_cache`` statistics.

    Returns:
        A ``CacheInfo`` named-tuple with fields ``hits``, ``misses``,
        ``maxsize``, and ``currsize``.
    """
    return _cached_extract_impl.cache_info()


def clear_cache() -> None:
    """Clear the extraction cache and reset the hit/miss counters."""
    _cached_extract_impl.cache_clear()
    logger.info("KG extraction cache cleared")
