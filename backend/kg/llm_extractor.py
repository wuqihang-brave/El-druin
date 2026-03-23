"""
LLM-based knowledge-graph extractor for EL'druin.

Wraps LangChain's ``LLMGraphTransformer`` (from ``langchain_experimental``)
to extract :class:`~kg.models.Triple` objects from news text.

Environment variables
---------------------
* ``GROQ_API_KEY``   – preferred; uses Groq's fast inference.
* ``OPENAI_API_KEY`` – fallback when Groq key is absent.
* ``LLM_MODEL``      – model name override (default varies by provider).

If neither key is present the extractor operates in *stub mode*, returning
an empty list with a warning rather than raising an error.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from dotenv import load_dotenv

from kg.models import (
    Entity,
    EntityType,
    Relation,
    RelationType,
    Triple,
)

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Controlled-vocabulary strings passed to LLMGraphTransformer
# ---------------------------------------------------------------------------

_ALLOWED_NODES: List[str] = [e.value for e in EntityType]

_ALLOWED_RELATIONSHIPS: List[str] = [r.value for r in RelationType]

# ---------------------------------------------------------------------------
# Mapping from LangChain graph objects to our domain models
# ---------------------------------------------------------------------------

_ENTITY_TYPE_MAP = {et.value.lower(): et for et in EntityType}
_RELATION_TYPE_MAP = {rt.value.lower(): rt for rt in RelationType}

_DEFAULT_ENTITY_TYPE = EntityType.ORGANIZATION
_DEFAULT_RELATION_TYPE = RelationType.RELATED_TO


def _map_entity_type(raw: str) -> EntityType:
    return _ENTITY_TYPE_MAP.get(raw.strip().lower(), _DEFAULT_ENTITY_TYPE)


def _map_relation_type(raw: str) -> RelationType:
    return _RELATION_TYPE_MAP.get(raw.strip().lower(), _DEFAULT_RELATION_TYPE)


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _build_llm():
    """Construct the best available LLM instance.

    Priority: Groq → OpenAI → None (stub mode).
    """
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if groq_key:
        try:
            from langchain_groq import ChatGroq  # type: ignore

            model = os.getenv("LLM_MODEL", "llama3-8b-8192")
            logger.info("Using Groq LLM: %s", model)
            return ChatGroq(api_key=groq_key, model_name=model, temperature=0)
        except ImportError:
            logger.warning("langchain-groq not installed; falling back to OpenAI")

    if openai_key:
        try:
            from langchain_openai import ChatOpenAI  # type: ignore

            model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
            logger.info("Using OpenAI LLM: %s", model)
            return ChatOpenAI(api_key=openai_key, model=model, temperature=0)
        except ImportError:
            logger.warning("langchain-openai not installed; running in stub mode")

    logger.warning(
        "No LLM API key found (GROQ_API_KEY / OPENAI_API_KEY). "
        "KGExtractor will return empty triples."
    )
    return None


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------

class KGExtractor:
    """Extract knowledge-graph triples from news text.

    Parameters
    ----------
    llm:
        Pre-built LangChain chat model.  When *None* the extractor attempts
        to construct one from environment variables.

    Examples
    --------
    >>> extractor = KGExtractor()
    >>> triples = extractor.extract("Apple CEO Tim Cook met with EU regulators.")
    >>> for t in triples:
    ...     print(t.subject_name, "→", t.relation_label, "→", t.object_name)
    """

    def __init__(self, llm=None) -> None:
        self._llm = llm or _build_llm()
        self._transformer: Optional[object] = None

        if self._llm is not None:
            self._transformer = self._build_transformer()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract(self, text: str) -> List[Triple]:
        """Extract triples from a single text snippet.

        Args:
            text: Raw news text (title + description recommended).

        Returns:
            List of :class:`~kg.models.Triple` objects. Empty list on error
            or when no LLM is available.
        """
        if not text or not text.strip():
            return []

        if self._transformer is None:
            logger.debug("No LLM available; returning empty triple list.")
            return []

        try:
            return self._run_transformer(text)
        except Exception as exc:
            logger.error("LLMGraphTransformer failed: %s", exc, exc_info=True)
            return []

    def extract_batch(self, texts: List[str]) -> List[Triple]:
        """Extract triples from a list of texts.

        Processes each text independently and merges the results.

        Args:
            texts: List of news text strings.

        Returns:
            Combined list of :class:`~kg.models.Triple` objects.
        """
        all_triples: List[Triple] = []
        for text in texts:
            triples = self.extract(text)
            all_triples.extend(triples)
        logger.info(
            "Batch extraction complete: %d texts → %d triples",
            len(texts),
            len(all_triples),
        )
        return all_triples

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_transformer(self):
        """Instantiate LLMGraphTransformer with controlled vocabularies."""
        try:
            from langchain_experimental.graph_transformers import (  # type: ignore
                LLMGraphTransformer,
            )

            return LLMGraphTransformer(
                llm=self._llm,
                allowed_nodes=_ALLOWED_NODES,
                allowed_relationships=_ALLOWED_RELATIONSHIPS,
                strict_mode=True,
            )
        except ImportError as exc:
            logger.error(
                "langchain-experimental is not installed (%s). "
                "Install it with: pip install langchain-experimental",
                exc,
            )
            return None

    def _run_transformer(self, text: str) -> List[Triple]:
        """Run the transformer and convert LangChain nodes/rels → Triples."""
        try:
            from langchain_core.documents import Document  # type: ignore
        except ImportError:
            from langchain.schema import Document  # type: ignore

        docs = [Document(page_content=text)]
        graph_docs = self._transformer.convert_to_graph_documents(docs)  # type: ignore[union-attr]

        triples: List[Triple] = []
        for gdoc in graph_docs:
            # Build an index of node objects for quick lookup
            node_map = {node.id: node for node in gdoc.nodes}

            for rel in gdoc.relationships:
                try:
                    triple = self._convert_relationship(rel, node_map, text)
                    triples.append(triple)
                except Exception as conv_exc:
                    logger.debug(
                        "Could not convert relationship %s: %s", rel, conv_exc
                    )

        logger.info("Extracted %d triples from text (%d chars)", len(triples), len(text))
        return triples

    def _convert_relationship(self, rel, node_map: dict, source_text: str) -> Triple:
        """Convert a LangChain Relationship to a :class:`~kg.models.Triple`."""
        src_node = node_map.get(rel.source.id, rel.source)
        tgt_node = node_map.get(rel.target.id, rel.target)

        subject = Entity(
            name=src_node.id,
            entity_type=_map_entity_type(getattr(src_node, "type", "")),
            description=getattr(src_node, "properties", {}).get("description"),
        )
        obj = Entity(
            name=tgt_node.id,
            entity_type=_map_entity_type(getattr(tgt_node, "type", "")),
            description=getattr(tgt_node, "properties", {}).get("description"),
        )
        relation = Relation(
            source=subject.name,
            target=obj.name,
            relation_type=_map_relation_type(rel.type),
            description=getattr(rel, "properties", {}).get("description"),
        )
        return Triple(
            subject=subject,
            predicate=relation,
            obj=obj,
            source_text=source_text[:500],
        )
