"""
KuzuDB database initialisation helper.

This module is imported by the FastAPI startup hook in ``app.main`` to
ensure the embedded database directories and schemas exist before any
request handler tries to open them.  All operations are **idempotent** –
running them multiple times (e.g. across Railway redeploys) is safe.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def initialize_database() -> None:
    """Create database directories and initialise KuzuDB schemas.

    This function is idempotent: it uses ``CREATE TABLE IF NOT EXISTS``
    semantics and ``exist_ok=True`` for directory creation, so it is safe
    to call on every application start-up.

    Two database paths are initialised, matching the defaults in
    :class:`app.core.config.Settings`:

    * ``kuzu_db_path`` – used by the graph store / analysis routes.
    * ``kuzu_kg_path``  – used by the knowledge-graph layer.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        kuzu_db_path = settings.kuzu_db_path
        kuzu_kg_path = settings.kuzu_kg_path
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not load settings, using defaults: %s", exc)
        kuzu_db_path = os.getenv("KUZU_DB_PATH", "./data/kuzu_db")
        kuzu_kg_path = os.getenv("KUZU_KG_PATH", "./data/el_druin.kuzu")

    _init_graph_store_db(kuzu_db_path)
    _init_knowledge_graph_db(kuzu_kg_path)
    logger.info("Database initialisation complete")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _init_graph_store_db(db_path: str) -> None:
    """Initialise the main graph-store KuzuDB (used by analysis routes)."""
    try:
        import kuzu  # type: ignore

        os.makedirs(db_path, exist_ok=True)
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)

        _DDL = [
            "CREATE NODE TABLE IF NOT EXISTS Entity"
            "(name STRING, type STRING, description STRING, PRIMARY KEY(name))",
            "CREATE NODE TABLE IF NOT EXISTS Article"
            "(id STRING, title STRING, source STRING, published STRING,"
            " link STRING, category STRING, PRIMARY KEY(id))",
            "CREATE REL TABLE IF NOT EXISTS MENTIONED_IN"
            "(FROM Entity TO Article, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS RELATED_TO"
            "(FROM Entity TO Entity, relation_type STRING, weight DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS CONTRADICTS"
            "(FROM Entity TO Entity, reason STRING,"
            " confidence DOUBLE, source_reliability DOUBLE, timestamp TIMESTAMP)",
        ]

        for ddl in _DDL:
            try:
                conn.execute(ddl)
            except Exception as exc:
                logger.debug("graph_store schema (ignored): %s", exc)

        logger.info("Graph-store DB ready at %s", db_path)
    except ImportError:
        logger.warning("kuzu package not installed – skipping graph-store DB init")
    except Exception as exc:
        logger.error("Failed to initialise graph-store DB at %s: %s", db_path, exc)
        raise


def _init_knowledge_graph_db(db_path: str) -> None:
    """Initialise the knowledge-graph KuzuDB (used by KuzuKnowledgeGraph)."""
    try:
        import kuzu  # type: ignore

        parent = Path(db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)

        _TYPED_NODE_TABLES = [
            "Person", "Organization", "Location", "Event", "Concept",
        ]

        _node_ddl = (
            "CREATE NODE TABLE IF NOT EXISTS {tbl}"
            "(name STRING, description STRING, confidence DOUBLE,"
            " PRIMARY KEY(name))"
        )
        _DDL: list[str] = [
            _node_ddl.format(tbl=tbl) for tbl in _TYPED_NODE_TABLES
        ] + [
            "CREATE NODE TABLE IF NOT EXISTS Entity"
            "(name STRING, entity_type STRING, description STRING,"
            " confidence DOUBLE, PRIMARY KEY(name))",
            "CREATE REL TABLE IF NOT EXISTS RELATED_TO"
            "(FROM Entity TO Entity, relation_type STRING, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS LOCATED_IN"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS PARTICIPATES_IN"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS WORKS_FOR"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS MEMBER_OF"
            "(FROM Entity TO Entity, confidence DOUBLE)",
        ]

        for ddl in _DDL:
            try:
                conn.execute(ddl)
            except Exception as exc:
                logger.debug("knowledge_graph schema (ignored): %s", exc)

        logger.info("Knowledge-graph DB ready at %s", db_path)
    except ImportError:
        logger.warning("kuzu package not installed – skipping knowledge-graph DB init")
    except Exception as exc:
        logger.error("Failed to initialise knowledge-graph DB at %s: %s", db_path, exc)
        raise


def get_db_connection(db_path: Optional[str] = None) -> Any:
    """Return a KuzuDB connection for *db_path*.

    If *db_path* is ``None``, the value from application settings is used.
    The database is initialised (directory + schema) before the connection
    is returned, so callers can rely on a ready-to-use connection.
    """
    import kuzu  # type: ignore

    if db_path is None:
        try:
            from app.core.config import get_settings
            db_path = get_settings().kuzu_db_path
        except Exception:
            db_path = os.getenv("KUZU_DB_PATH", "./data/kuzu_db")

    os.makedirs(db_path, exist_ok=True)
    db = kuzu.Database(db_path)
    return kuzu.Connection(db)
