"""Built-in command surface for EL-DRUIN knowledge-graph operations."""

from __future__ import annotations

from .models import PortingBacklog, PortingModule

# ---------------------------------------------------------------------------
# Canonical set of built-in pipeline commands.
# Each entry mirrors a backend capability exposed through the API.
# ---------------------------------------------------------------------------

_BUILTIN_COMMANDS: tuple[PortingModule, ...] = (
    PortingModule(
        name="extract_triples",
        responsibility="Extract entity/relation triples from raw text",
        source_hint="app.knowledge.entity_extractor",
        status="active",
    ),
    PortingModule(
        name="query_graph",
        responsibility="Run a Cypher query against the KuzuDB knowledge graph",
        source_hint="app.knowledge.kuzu_graph",
        status="active",
    ),
    PortingModule(
        name="list_entities",
        responsibility="List entity nodes currently stored in the knowledge graph",
        source_hint="app.knowledge.graph_store",
        status="active",
    ),
    PortingModule(
        name="list_relations",
        responsibility="List relation edges currently stored in the knowledge graph",
        source_hint="app.knowledge.graph_store",
        status="active",
    ),
    PortingModule(
        name="ingest_text",
        responsibility="Ingest news text and persist extracted triples to the KG",
        source_hint="app.knowledge.knowledge_graph",
        status="active",
    ),
    PortingModule(
        name="audit_report",
        responsibility="Run the Bayesian audit pipeline on a news report",
        source_hint="intelligence.logic_auditor",
        status="active",
    ),
    PortingModule(
        name="get_reasoning_path",
        responsibility="Retrieve a completed reasoning path by its UUID",
        source_hint="intelligence.logic_auditor",
        status="active",
    ),
    PortingModule(
        name="get_probability_tree",
        responsibility="Retrieve the probability tree for an intelligence report",
        source_hint="intelligence.probability_tree",
        status="active",
    ),
    PortingModule(
        name="filter_triples",
        responsibility="Score and filter triples using the Order Critic Agent",
        source_hint="knowledge_layer.order_critic",
        status="active",
    ),
    PortingModule(
        name="hierarchical_graph",
        responsibility="Return degree-filtered hierarchical graph for visualisation",
        source_hint="app.api.routes.knowledge",
        status="active",
    ),
)


def build_command_backlog() -> PortingBacklog:
    """Return a :class:`PortingBacklog` containing all built-in commands."""
    return PortingBacklog(title="Command surface", modules=list(_BUILTIN_COMMANDS))


def get_command(name: str) -> PortingModule | None:
    """Look up a command by name (case-insensitive).

    Returns ``None`` if no matching command is found.
    """
    needle = name.lower()
    for cmd in _BUILTIN_COMMANDS:
        if cmd.name.lower() == needle:
            return cmd
    return None
