"""
Seed Ontology – Initialize KuzuDB with realistic entities and relationships

Provides seed data for geopolitics, technology/AI, and economy domains.
Uses idempotent MERGE patterns to prevent duplicates.

Run with::

    python -m backend.knowledge_layer.seed_ontology

Example entities seeded:
- North Korea --strategic_alliance--> Russia (strength 0.95)
- Kim Jong-un --role--> Supreme Leader of North Korea
- Belarus --ally--> Russia
- Lukashenko --role--> President of Belarus
- AI_data_centers --causes--> job_displacement (strength 0.85)
- Sen_Mark_Warner --position--> US Senator
- Data centers --tax_proposal--> worker_transition_fund
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

def _ensure_backend_importable() -> None:
    """Add backend to sys.path if needed."""
    here = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


class SeedOntologySeeder:
    """Seeds realistic ontological data into KuzuDB."""

    def __init__(self, db_path: str = "./data/kuzu_db") -> None:
        """Initialize seeder with KuzuDB connection."""
        try:
            import kuzu  # type: ignore
            os.makedirs(db_path, exist_ok=True)
            self._db = kuzu.Database(db_path)
            self._conn = kuzu.Connection(self._db)
            self._available = True
        except ImportError:
            logger.error("kuzu package not installed")
            self._available = False
            self._conn = None
        except Exception as exc:
            logger.error("Failed to connect to KuzuDB: %s", exc)
            self._available = False
            self._conn = None

        self.entities_created = 0
        self.relationships_created = 0

    def _ensure_schema(self) -> None:
        """Ensure basic schema exists (idempotent)."""
        if not self._available or not self._conn:
            return

        ddl_stmts = [
            "CREATE NODE TABLE IF NOT EXISTS Entity"
            "(name STRING PRIMARY KEY, type STRING, description STRING, virtue STRING, role STRING)",
            "CREATE REL TABLE IF NOT EXISTS RELATED(FROM Entity TO Entity, relation_type STRING, strength DOUBLE)",
        ]

        for stmt in ddl_stmts:
            try:
                self._conn.execute(stmt)
            except Exception as exc:
                logger.debug("Schema statement (idempotent): %s", exc)

    def seed_entities(self) -> Tuple[int, List[str]]:
        """Seed core entities across three domains.

        Returns:
            (count, list_of_entity_names)
        """
        if not self._available or not self._conn:
            logger.warning("KuzuDB not available; skipping entity seeding")
            return 0, []

        entities: List[Tuple[str, str, str, Optional[str], Optional[str]]] = [
            # GEOPOLITICS: Strategic actors
            ("North Korea", "GPE", "Democratic People's Republic of Korea", None, None),
            ("Russia", "GPE", "Russian Federation", None, None),
            ("Belarus", "GPE", "Republic of Belarus", None, None),
            ("USA", "GPE", "United States of America", None, None),
            ("China", "GPE", "People's Republic of China", None, None),
            ("European Union", "ORG", "Political and economic union of 27 states", None, None),

            # GEOPOLITICS: Key decision-makers
            ("Kim Jong-un", "PERSON", "Supreme Leader of North Korea", "strategic resilience", "Supreme Leader"),
            ("Vladimir Putin", "PERSON", "President of Russian Federation", "power consolidation", "President"),
            ("Alexander Lukashenko", "PERSON", "President of Belarus", "regime stability", "President"),
            ("Joe Biden", "PERSON", "President of USA", "democratic order", "President"),
            ("Xi Jinping", "PERSON", "General Secretary of CCP", "regional dominance", "General Secretary"),

            # TECHNOLOGY/AI: Institutions and actors
            ("OpenAI", "ORG", "AI research laboratory", None, None),
            ("DeepMind", "ORG", "AI research division of Alphabet", None, None),
            ("Google", "ORG", "Technology and AI conglomerate", None, None),
            ("Meta", "ORG", "Social media and AI company", None, None),
            ("Sen Mark Warner", "PERSON", "US Senator, technology regulation advocate", "tech regulation", "US Senator"),

            # TECHNOLOGY/AI: Concepts and sectors
            ("Artificial Intelligence", "CONCEPT", "Machine learning and intelligent systems", None, None),
            ("AI Data Centers", "CONCEPT", "Infrastructure for AI computation", None, None),
            ("Job Displacement", "CONCEPT", "Technological unemployment and workforce disruption", None, None),
            ("Data Privacy", "CONCEPT", "Protection of personal data", None, None),
            ("AI Regulation", "CONCEPT", "Government policy for AI governance", None, None),

            # ECONOMY: Financial actors and concepts
            ("Federal Reserve", "ORG", "US central bank", None, None),
            ("European Central Bank", "ORG", "Central bank of the Eurozone", None, None),
            ("Tech Stocks", "CONCEPT", "Equity securities of technology companies", None, None),
            ("Inflation", "CONCEPT", "Rise in general price level of goods and services", None, None),
            ("Interest Rates", "CONCEPT", "Cost of borrowing money", None, None),
            ("Worker Transition Fund", "CONCEPT", "Policy funding job retraining and support", None, None),
        ]

        count = 0
        names = []
        for name, etype, desc, virtue, role in entities:
            names.append(name)
            try:
                escaped_name = name.replace("'", "\\'")
                escaped_desc = desc.replace("'", "\\'") if desc else ""
                escaped_virtue = virtue.replace("'", "\\'") if virtue else "NULL"
                escaped_role = role.replace("'", "\\'") if role else "NULL"

                query = (
                    f"MERGE (e:Entity {{name: '{{escaped_name}}'}}) "
                    f"ON CREATE SET e.type = '{{etype}}', e.description = '{{escaped_desc}}', "
                    f"e.virtue = {{escaped_virtue if escaped_virtue != 'NULL' else 'NULL'}}, "
                    f"e.role = {{escaped_role if escaped_role != 'NULL' else 'NULL'}} "
                    f"RETURN e.name"
                )
                result = self._conn.execute(query)
                if result.has_next():
                    count += 1
                    logger.debug("Seeded entity: %s", name)
            except Exception as exc:
                logger.debug("Entity seed (may be duplicate): %s – %s", name, exc)

        self.entities_created = count
        logger.info("Seeded %d entities", count)
        return count, names

    def seed_relationships(self, entity_names: List[str]) -> int:
        """Seed relationships across domains (1-hop and 2-hop).

        Args:
            entity_names: List of entity names available for relationships.

        Returns:
            Count of relationships created.
        """
        if not self._available or not self._conn:
            logger.warning("KuzuDB not available; skipping relationship seeding")
            return 0

        # Define relationships as (source, target, relation_type, strength)
        relationships: List[Tuple[str, str, str, float]] = [
            # GEOPOLITICS: Strategic alliances
            ("North Korea", "Russia", "strategic_alliance", 0.95),
            ("Belarus", "Russia", "ally", 0.90),
            ("China", "Russia", "strategic_partner", 0.85),
            ("Russia", "European Union", "confrontation", 0.80),
            ("USA", "European Union", "ally", 0.95),

            # GEOPOLITICS: Leadership and governance
            ("Kim Jong-un", "North Korea", "leads", 1.0),
            ("Vladimir Putin", "Russia", "leads", 1.0),
            ("Alexander Lukashenko", "Belarus", "leads", 1.0),
            ("Joe Biden", "USA", "leads", 1.0),
            ("Xi Jinping", "China", "leads", 1.0),

            # TECHNOLOGY/AI: Institutional relationships
            ("OpenAI", "Artificial Intelligence", "develops", 0.95),
            ("DeepMind", "Artificial Intelligence", "advances", 0.95),
            ("Google", "DeepMind", "owns", 1.0),
            ("Meta", "Artificial Intelligence", "invests", 0.85),
            ("Google", "AI Data Centers", "operates", 0.90),

            # TECHNOLOGY/AI: Impact relationships (causality)
            ("AI Data Centers", "Job Displacement", "causes", 0.85),
            ("Artificial Intelligence", "Data Privacy", "threatens", 0.75),
            ("Artificial Intelligence", "AI Regulation", "triggers", 0.80),
            ("Sen Mark Warner", "AI Regulation", "advocates", 0.90),

            # ECONOMY: Monetary policy
            ("Federal Reserve", "Interest Rates", "controls", 1.0),
            ("European Central Bank", "Interest Rates", "controls", 1.0),
            ("Interest Rates", "Tech Stocks", "influences", 0.85),
            ("Inflation", "Interest Rates", "drives", 0.80),

            # ECONOMY: Policy and support
            ("Data Privacy", "AI Regulation", "motivates", 0.85),
            ("Job Displacement", "Worker Transition Fund", "justifies", 0.90),
            ("AI Data Centers", "Worker Transition Fund", "necessitates", 0.75),
        ]

        count = 0
        for source, target, rel_type, strength in relationships:
            try:
                escaped_source = source.replace("'", "\\'")
                escaped_target = target.replace("'", "\\'")
                escaped_rel = rel_type.replace("'", "\\'")

                query = (
                    f"MATCH (s:Entity {{name: '{{escaped_source}}'}}), "
                    f"(t:Entity {{name: '{{escaped_target}}'}}) "
                    f"MERGE (s)-[r:RELATED {{relation_type: '{{escaped_rel}}'}}]->(t) "
                    f"ON CREATE SET r.strength = {{strength}} "
                    f"RETURN r.relation_type"
                )
                result = self._conn.execute(query)
                if result.has_next():
                    count += 1
                    logger.debug("Seeded relationship: %s --%s--> %s (%.2f)", source, rel_type, target, strength)
            except Exception as exc:
                logger.debug("Relationship seed (may be duplicate): %s -> %s – %s", source, target, exc)

        self.relationships_created = count
        logger.info("Seeded %d relationships", count)
        return count

    def seed_ontology(self) -> Tuple[int, int]:
        """Run full seeding pipeline.

        Returns:
            (entities_created, relationships_created)
        """
        if not self._available:
            logger.error("KuzuDB not available – cannot seed")
            return 0, 0

        logger.info("Starting ontology seeding…")
        self._ensure_schema()

        ent_count, entity_names = self.seed_entities()
        rel_count = self.seed_relationships(entity_names)

        logger.info(
            "✅ Ontology seeding complete: %d entities + %d relationships",
            ent_count,
            rel_count,
        )
        return ent_count, rel_count


def main() -> None:
    """Entry point for seed_ontology module."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    )

    _ensure_backend_importable()

    seeder = SeedOntologySeeder(db_path="./data/kuzu_db")
    if not seeder._available:
        logger.error("KuzuDB connection failed – cannot proceed")
        sys.exit(1)

    ent_count, rel_count = seeder.seed_ontology()

    print()
    print("=" * 70)
    print("🎯 SEED ONTOLOGY COMPLETE")
    print("=" * 70)
    print(f"📊 Entities created: {{ent_count}}")
    print(f"🔗 Relationships created: {{rel_count}}")
    print(f"⏰ Timestamp: {{datetime.now().isoformat()}}")
    print("=" * 70)


if __name__ == "__main__":
    main()