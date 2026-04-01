"""Workspace port manifest – structured description of all backend subsystems."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Subsystem


@dataclass
class PortManifest:
    """Structured manifest of all backend subsystems included in the port."""

    title: str
    subsystems: list[Subsystem] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the manifest as a Markdown string."""
        lines = [f"## {self.title}", ""]
        for sub in self.subsystems:
            lines.append(f"### {sub.name} ({sub.file_count} files)")
            if sub.notes:
                lines.append(f"> {sub.notes}")
            lines.append(f"Path: `{sub.path}`")
            lines.append("")
        return "\n".join(lines)


def build_port_manifest() -> PortManifest:
    """Return the canonical :class:`PortManifest` for the EL-DRUIN backend."""
    return PortManifest(
        title="EL-DRUIN Backend Porting Manifest",
        subsystems=[
            Subsystem(
                name="Knowledge Graph",
                path="backend/app/knowledge",
                file_count=4,
                notes="Entity/relation storage, KuzuDB graph, and knowledge-graph facade.",
            ),
            Subsystem(
                name="Intelligence",
                path="backend/intelligence",
                file_count=10,
                notes=(
                    "Bayesian reasoning pipeline: logic auditor, probability trees, "
                    "sacred-sword analyser, multi-agent engine."
                ),
            ),
            Subsystem(
                name="Knowledge Layer",
                path="backend/knowledge_layer",
                file_count=6,
                notes=(
                    "Incremental entity resolution, causal-chain extraction, "
                    "order critic agent, KuzuDB store."
                ),
            ),
            Subsystem(
                name="Ontology",
                path="backend/ontology",
                file_count=2,
                notes="Relation schema definitions and KuzuDB context extractor.",
            ),
            Subsystem(
                name="API Routes",
                path="backend/app/api/routes",
                file_count=8,
                notes="FastAPI endpoint handlers for knowledge, intelligence, and provenance.",
            ),
            Subsystem(
                name="CLAW Integration",
                path="backend/app/claw_integration",
                file_count=9,
                notes="Tool porting layer: query engine, tool registry, task state machine.",
            ),
        ],
    )
