"""
import_schemaorg.py
==================
Idempotent schema.org type-hierarchy importer for KuzuDB.

Reads ``backend/ontology/resources/schemaorg_nodes.json`` and writes:

* ``SchemaType`` node table  – one node per schema.org type
* ``SUBTYPE_OF`` rel table   – directed edges child → parent

Usage (CLI)::

    # From the repo root:
    python -m backend.ontology.tools.import_schemaorg

    # With explicit DB path:
    python -m backend.ontology.tools.import_schemaorg --db ./data/el_druin.kuzu

    # Limit to first N types (useful for testing):
    python -m backend.ontology.tools.import_schemaorg --limit 100

    # Drop and recreate tables before import:
    python -m backend.ontology.tools.import_schemaorg --reset

The importer is safe to re-run multiple times (idempotent).

Schema
------
SchemaType node table::

    (name STRING, description STRING, schema_url STRING, PRIMARY KEY(name))

SUBTYPE_OF rel table::

    (FROM SchemaType TO SchemaType)

Multi-parent strings like "CreativeWork, MediaObject" are split on commas
so that a single child node can have multiple SUBTYPE_OF edges.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Locate repo root relative to this file:
# backend/ontology/tools/import_schemaorg.py
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]  # El-druin/
_DEFAULT_NODES_JSON = (
    _REPO_ROOT / "backend" / "ontology" / "resources" / "schemaorg_nodes.json"
)
_DEFAULT_DB_PATH = str(_REPO_ROOT / "data" / "el_druin.kuzu")

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL_SCHEMA_TYPE = (
    "CREATE NODE TABLE IF NOT EXISTS SchemaType"
    "(name STRING, description STRING, schema_url STRING, PRIMARY KEY(name))"
)

_DDL_SUBTYPE_OF = (
    "CREATE REL TABLE IF NOT EXISTS SUBTYPE_OF"
    "(FROM SchemaType TO SchemaType)"
)

_DDL_ENTITY_SCHEMA_TYPE = (
    "CREATE REL TABLE IF NOT EXISTS INSTANCE_OF"
    "(FROM Entity TO SchemaType, confidence DOUBLE)"
)

#: Maximum characters kept from a schema.org description when writing to Kuzu.
MAX_DESCRIPTION_LENGTH = 500

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_schema_url(parent_url: str) -> List[str]:
    """Extract type label(s) from a schema.org URL or comma-separated list.

    Examples::

        "https://schema.org/Person"          → ["Person"]
        "https://schema.org/CreativeWork, https://schema.org/MediaObject"
                                             → ["CreativeWork", "MediaObject"]
        "CreativeWork, MediaObject"          → ["CreativeWork", "MediaObject"]
        ""                                   → []
    """
    if not parent_url or not parent_url.strip():
        return []

    parts: List[str] = []
    for raw in parent_url.split(","):
        raw = raw.strip()
        if not raw:
            continue
        # Strip URL prefix
        label = re.sub(r"^https?://schema\.org/", "", raw).strip()
        if label:
            parts.append(label)
    return parts


def _escape_cypher(text: str) -> str:
    """Escape for embedding in Kuzu Cypher string literals."""
    return text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


# ---------------------------------------------------------------------------
# Schema init
# ---------------------------------------------------------------------------


def init_schema_tables(conn: "kuzu.Connection", reset: bool = False) -> None:  # type: ignore[name-defined]
    """Create SchemaType and SUBTYPE_OF tables (and INSTANCE_OF if needed).

    Parameters
    ----------
    conn:
        Open KuzuDB connection.
    reset:
        If True, drop existing SchemaType and SUBTYPE_OF tables first
        (allows a clean reimport).  Use with care.
    """
    if reset:
        for stmt in (
            "DROP TABLE IF EXISTS SUBTYPE_OF",
            "DROP TABLE IF EXISTS INSTANCE_OF",
            "DROP TABLE IF EXISTS SchemaType",
        ):
            try:
                conn.execute(stmt)
                logger.info("Dropped table: %s", stmt.split()[-1])
            except Exception as exc:
                logger.debug("Drop failed (ignored): %s", exc)

    for stmt in (_DDL_SCHEMA_TYPE, _DDL_SUBTYPE_OF, _DDL_ENTITY_SCHEMA_TYPE):
        try:
            conn.execute(stmt)
        except Exception as exc:
            logger.debug("Schema init (ignored): %s", exc)


# ---------------------------------------------------------------------------
# Core import logic
# ---------------------------------------------------------------------------


def import_schemaorg(
    conn: "kuzu.Connection",  # type: ignore[name-defined]
    nodes_json_path: Optional[str] = None,
    limit: Optional[int] = None,
    reset: bool = False,
) -> Tuple[int, int]:
    """Import schema.org type hierarchy into KuzuDB.

    Parameters
    ----------
    conn:
        Open KuzuDB connection.
    nodes_json_path:
        Path to ``schemaorg_nodes.json``.  Defaults to the repo-relative path
        ``backend/ontology/resources/schemaorg_nodes.json``.
    limit:
        If set, import only the first *limit* type entries (useful for testing).
    reset:
        If True, drop and recreate SchemaType/SUBTYPE_OF tables before import.

    Returns
    -------
    (nodes_written, edges_written)
    """
    json_path = nodes_json_path or str(_DEFAULT_NODES_JSON)
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"schemaorg_nodes.json not found at: {json_path}\n"
            "Run tools/generate_schemaorg_ontology.py to regenerate it, or\n"
            "ensure backend/ontology/resources/schemaorg_nodes.json is present."
        )

    logger.info("Loading schema.org nodes from: %s", json_path)
    with open(json_path, encoding="utf-8") as fh:
        nodes: Dict[str, dict] = json.load(fh)

    if limit is not None:
        # Take first `limit` entries (dict ordering is stable in Python 3.7+)
        nodes = dict(list(nodes.items())[:limit])

    logger.info("Loaded %d schema.org type entries", len(nodes))

    # Ensure tables exist
    init_schema_tables(conn, reset=reset)

    # ── Pass 1: Insert SchemaType nodes ──────────────────────────────────────
    nodes_written = 0
    for type_name, meta in nodes.items():
        name_esc = _escape_cypher(type_name)
        desc = str(meta.get("description", "") or "").replace("\n", " ")[:MAX_DESCRIPTION_LENGTH]
        desc_esc = _escape_cypher(desc)
        url = str(meta.get("schema_url", "") or "")
        url_esc = _escape_cypher(url)

        try:
            conn.execute(
                f"CREATE (:SchemaType {{name: '{name_esc}',"
                f" description: '{desc_esc}', schema_url: '{url_esc}'}})"
            )
            nodes_written += 1
        except Exception as exc:
            if "duplicated primary key" in str(exc).lower():
                logger.debug("SchemaType '%s' already exists – skipped", type_name)
            else:
                logger.warning("Failed to insert SchemaType '%s': %s", type_name, exc)

    logger.info("SchemaType nodes written: %d (of %d)", nodes_written, len(nodes))

    # ── Pass 2: Insert SUBTYPE_OF edges ──────────────────────────────────────
    edges_written = 0
    for type_name, meta in nodes.items():
        parent_raw = str(meta.get("parent", "") or "")
        parents = _strip_schema_url(parent_raw)

        for parent_name in parents:
            if parent_name not in nodes:
                logger.debug(
                    "SUBTYPE_OF skipped: '%s' parent '%s' not in loaded nodes",
                    type_name,
                    parent_name,
                )
                continue

            child_esc = _escape_cypher(type_name)
            parent_esc = _escape_cypher(parent_name)

            try:
                # Check if edge already exists
                check = conn.execute(
                    f"MATCH (c:SchemaType {{name: '{child_esc}'}})"
                    f" MATCH (p:SchemaType {{name: '{parent_esc}'}})"
                    f" MATCH (c)-[r:SUBTYPE_OF]->(p)"
                    f" RETURN count(r)"
                )
                if check.has_next() and check.get_next()[0] > 0:
                    logger.debug(
                        "SUBTYPE_OF '%s'→'%s' already exists – skipped",
                        type_name, parent_name,
                    )
                    continue

                conn.execute(
                    f"MATCH (c:SchemaType {{name: '{child_esc}'}})"
                    f" MATCH (p:SchemaType {{name: '{parent_esc}'}})"
                    f" CREATE (c)-[:SUBTYPE_OF]->(p)"
                )
                edges_written += 1
            except Exception as exc:
                logger.warning(
                    "Failed to insert SUBTYPE_OF '%s'→'%s': %s",
                    type_name, parent_name, exc,
                )

    logger.info(
        "SUBTYPE_OF edges written: %d", edges_written,
    )
    logger.info(
        "✅ schema.org import complete: %d nodes, %d edges",
        nodes_written, edges_written,
    )
    return nodes_written, edges_written


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description=(
            "Import schema.org type hierarchy into KuzuDB.\n"
            "Reads backend/ontology/resources/schemaorg_nodes.json and writes\n"
            "SchemaType nodes and SUBTYPE_OF edges into the target database."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db",
        default=_DEFAULT_DB_PATH,
        help=f"Path to KuzuDB directory (default: {_DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--nodes-json",
        default=str(_DEFAULT_NODES_JSON),
        help=f"Path to schemaorg_nodes.json (default: {_DEFAULT_NODES_JSON})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Import only first N types (useful for testing)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate SchemaType/SUBTYPE_OF tables before import",
    )

    args = parser.parse_args()

    try:
        import kuzu  # type: ignore
    except ImportError:
        print("ERROR: kuzu package is not installed. Run: pip install kuzu", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    db = kuzu.Database(args.db)
    conn = kuzu.Connection(db)

    try:
        nodes_written, edges_written = import_schemaorg(
            conn=conn,
            nodes_json_path=args.nodes_json,
            limit=args.limit,
            reset=args.reset,
        )
        print(
            f"\n✅ Import complete: {nodes_written} SchemaType nodes,"
            f" {edges_written} SUBTYPE_OF edges"
        )
        print(f"   Database: {args.db}")
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Import failed: {exc}", file=sys.stderr)
        logger.exception("Import failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
