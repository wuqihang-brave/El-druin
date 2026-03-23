"""
Tests for the Knowledge Layer (backend/kg) module.
====================================================

Validates:
* Data models (Entity, Relation, Triple)
* KGExtractor stub mode (no LLM key required)
* GraphBuilder – NetworkX and Kuzu (if available)
* Cache (@lru_cache) hit/miss behaviour
* Batch extraction

Run::

    cd backend
    python -m pytest test_kg_extractor.py -v
    # or directly:
    python test_kg_extractor.py
"""

from __future__ import annotations

import os
import sys
import time
import logging
import tempfile
from typing import List

# ---------------------------------------------------------------------------
# Make sure the backend package is importable regardless of CWD
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from kg.models import Entity, EntityType, Relation, RelationType, Triple
from kg.llm_extractor import KGExtractor
from kg.graph_builder import GraphBuilder
from kg.cache import cached_extract, cache_info, clear_cache


# ===========================================================================
# Helpers
# ===========================================================================

def _make_entity(name: str, etype: EntityType = EntityType.PERSON) -> Entity:
    return Entity(name=name, entity_type=etype)


def _make_triple(
    subj_name: str,
    obj_name: str,
    rel: RelationType = RelationType.WORKS_FOR,
) -> Triple:
    subj = _make_entity(subj_name, EntityType.PERSON)
    obj = _make_entity(obj_name, EntityType.ORGANIZATION)
    pred = Relation(source=subj_name, target=obj_name, relation_type=rel)
    return Triple(subject=subj, predicate=pred, obj=obj)


# ===========================================================================
# Test 1 – Data models
# ===========================================================================

def test_entity_model() -> bool:
    """Validate Entity model creation and enum values."""
    print("\n[Test 1a] Entity model")
    try:
        e = Entity(name="Tim Cook", entity_type=EntityType.PERSON)
        assert e.name == "Tim Cook"
        assert e.entity_type == EntityType.PERSON.value
        print(f"  ✅ Entity: {e.name} ({e.entity_type})")

        e2 = Entity(name="Apple", entity_type="Organization", description="Tech company")
        assert e2.entity_type == EntityType.ORGANIZATION.value
        print(f"  ✅ Entity from string type: {e2.name} ({e2.entity_type})")
        return True
    except Exception as exc:
        print(f"  ❌ Entity model test failed: {exc}")
        return False


def test_relation_model() -> bool:
    """Validate Relation model."""
    print("\n[Test 1b] Relation model")
    try:
        r = Relation(
            source="Tim Cook",
            target="Apple",
            relation_type=RelationType.WORKS_FOR,
        )
        assert r.source == "Tim Cook"
        assert r.target == "Apple"
        assert r.relation_type == RelationType.WORKS_FOR.value
        print(f"  ✅ Relation: {r.source} --{r.relation_type}--> {r.target}")
        return True
    except Exception as exc:
        print(f"  ❌ Relation model test failed: {exc}")
        return False


def test_triple_model() -> bool:
    """Validate Triple model and convenience properties."""
    print("\n[Test 1c] Triple model")
    try:
        t = _make_triple("Tim Cook", "Apple")
        assert t.subject_name == "Tim Cook"
        assert t.object_name == "Apple"
        assert t.relation_label == RelationType.WORKS_FOR.value
        assert 0.0 <= t.confidence <= 1.0
        print(
            f"  ✅ Triple: {t.subject_name} --{t.relation_label}--> "
            f"{t.object_name} (conf={t.confidence})"
        )
        return True
    except Exception as exc:
        print(f"  ❌ Triple model test failed: {exc}")
        return False


# ===========================================================================
# Test 2 – KGExtractor (stub mode)
# ===========================================================================

def test_extractor_stub_mode() -> bool:
    """KGExtractor returns empty list when no LLM API key is set."""
    print("\n[Test 2a] KGExtractor stub mode")
    # Temporarily remove API keys to force stub behaviour
    saved = {}
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY"):
        saved[key] = os.environ.pop(key, None)

    try:
        extractor = KGExtractor(llm=None)
        result = extractor.extract("Apple CEO Tim Cook met with EU regulators in Brussels.")
        assert isinstance(result, list), "extract() must return a list"
        print(f"  ✅ Stub mode returned {len(result)} triples (expected 0 without LLM key)")
        return True
    except Exception as exc:
        print(f"  ❌ KGExtractor stub test failed: {exc}")
        return False
    finally:
        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val


def test_extractor_empty_input() -> bool:
    """Empty / whitespace-only input returns empty list."""
    print("\n[Test 2b] KGExtractor empty input")
    try:
        extractor = KGExtractor(llm=None)
        assert extractor.extract("") == []
        assert extractor.extract("   ") == []
        print("  ✅ Empty input handled correctly")
        return True
    except Exception as exc:
        print(f"  ❌ Empty input test failed: {exc}")
        return False


def test_extractor_batch() -> bool:
    """Batch extraction processes multiple texts."""
    print("\n[Test 2c] KGExtractor batch extraction")
    try:
        extractor = KGExtractor(llm=None)
        texts = [
            "NATO summit addresses European security.",
            "Fed raises interest rates amid inflation concerns.",
            "Tesla opens new Gigafactory in Texas.",
        ]
        result = extractor.extract_batch(texts)
        assert isinstance(result, list)
        print(f"  ✅ Batch extraction: {len(texts)} texts → {len(result)} triples")
        return True
    except Exception as exc:
        print(f"  ❌ Batch extraction test failed: {exc}")
        return False


# ===========================================================================
# Test 3 – GraphBuilder (NetworkX, optional Kuzu)
# ===========================================================================

def test_graph_builder_networkx() -> bool:
    """GraphBuilder correctly adds triples to NetworkX DiGraph."""
    print("\n[Test 3a] GraphBuilder – NetworkX")
    try:
        builder = GraphBuilder(kuzu_db_path=None)  # disable Kuzu for this test

        triples = [
            _make_triple("Tim Cook", "Apple"),
            _make_triple("Sundar Pichai", "Google"),
            _make_triple("Elon Musk", "Tesla"),
        ]
        builder.add_triples(triples)

        G = builder.get_networkx_graph()
        assert G.number_of_nodes() == 6
        assert G.number_of_edges() == 3

        # Check edge data
        edge_data = G.edges["Tim Cook", "Apple"]
        assert edge_data["relation_type"] == RelationType.WORKS_FOR.value

        summary = builder.summary()
        assert summary["nodes"] == 6
        assert summary["edges"] == 3
        print(
            f"  ✅ NetworkX graph: {summary['nodes']} nodes, "
            f"{summary['edges']} edges, density={summary['density']:.4f}"
        )
        return True
    except Exception as exc:
        print(f"  ❌ NetworkX test failed: {exc}")
        return False


def test_graph_builder_query_neighbors() -> bool:
    """query_neighbors returns correct adjacency information."""
    print("\n[Test 3b] GraphBuilder – query_neighbors")
    try:
        builder = GraphBuilder(kuzu_db_path=None)
        builder.add_triple(_make_triple("Tim Cook", "Apple"))
        builder.add_triple(_make_triple("Tim Cook", "Apple Inc.", RelationType.MANAGES))

        neighbors = builder.query_neighbors("Tim Cook")
        assert len(neighbors) >= 1

        filtered = builder.query_neighbors("Tim Cook", relation_type="MANAGES")
        assert any("Apple Inc." in (s + t) for s, t, _ in filtered)
        print(f"  ✅ query_neighbors returned {len(neighbors)} results")
        return True
    except Exception as exc:
        print(f"  ❌ query_neighbors test failed: {exc}")
        return False


def test_graph_builder_kuzu() -> bool:
    """GraphBuilder writes to Kuzu when package is available."""
    print("\n[Test 3c] GraphBuilder – Kuzu (optional)")
    try:
        import kuzu  # type: ignore  # noqa: F401 – just checking availability
    except ImportError:
        print("  ⚠️  kuzu not installed – skipping Kuzu persistence test")
        return True  # Not a failure; Kuzu is optional

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = GraphBuilder(kuzu_db_path=tmpdir)
            triples = [
                _make_triple("Angela Merkel", "Germany", RelationType.MANAGES),
                _make_triple("Emmanuel Macron", "France", RelationType.MANAGES),
            ]
            builder.add_triples(triples)
            summary = builder.summary()
            assert summary["nodes"] >= 2
            builder.close()
        print(f"  ✅ Kuzu persistence test passed ({summary['nodes']} nodes)")
        return True
    except Exception as exc:
        print(f"  ❌ Kuzu persistence test failed: {exc}")
        return False


# ===========================================================================
# Test 4 – Cache
# ===========================================================================

def test_cache_hit_miss() -> bool:
    """@lru_cache hit/miss counts are tracked correctly."""
    print("\n[Test 4a] Cache – hit/miss")
    try:
        clear_cache()
        info_before = cache_info()
        assert info_before.hits == 0
        assert info_before.misses == 0

        text = "NATO foreign ministers meet in Brussels to discuss defence spending."

        # First call – cache miss
        result1 = cached_extract(text)
        info_after_first = cache_info()
        assert info_after_first.misses == 1
        assert info_after_first.hits == 0

        # Second call – cache hit
        result2 = cached_extract(text)
        info_after_second = cache_info()
        assert info_after_second.hits == 1
        assert info_after_second.misses == 1

        assert result1 == result2
        print(
            f"  ✅ Cache stats after 2 calls: "
            f"hits={info_after_second.hits}, misses={info_after_second.misses}"
        )
        return True
    except Exception as exc:
        print(f"  ❌ Cache hit/miss test failed: {exc}")
        return False


def test_cache_normalisation() -> bool:
    """Normalised text shares cache entry with original."""
    print("\n[Test 4b] Cache – text normalisation")
    try:
        clear_cache()

        text1 = "  NATO foreign ministers meet.  "
        text2 = "nato foreign ministers meet."  # lowercase equivalent

        cached_extract(text1)
        cached_extract(text2)

        info = cache_info()
        # Both normalise to the same key → 1 miss, 1 hit
        assert info.misses == 1
        assert info.hits == 1
        print(
            f"  ✅ Normalisation works: {info.misses} miss(es), {info.hits} hit(s)"
        )
        return True
    except Exception as exc:
        print(f"  ❌ Cache normalisation test failed: {exc}")
        return False


def test_cache_empty_input() -> bool:
    """cached_extract handles empty/whitespace input gracefully."""
    print("\n[Test 4c] Cache – empty input")
    try:
        result = cached_extract("")
        assert result == []
        result2 = cached_extract("   ")
        assert result2 == []
        print("  ✅ Empty input returns []")
        return True
    except Exception as exc:
        print(f"  ❌ Cache empty input test failed: {exc}")
        return False


def test_cache_clear() -> bool:
    """clear_cache resets hit/miss counters."""
    print("\n[Test 4d] Cache – clear")
    try:
        cached_extract("Some text to populate the cache.")
        clear_cache()
        info = cache_info()
        assert info.hits == 0
        assert info.misses == 0
        print("  ✅ Cache cleared successfully")
        return True
    except Exception as exc:
        print(f"  ❌ Cache clear test failed: {exc}")
        return False


# ===========================================================================
# Test 5 – Entity type controlled vocabulary
# ===========================================================================

def test_entity_type_validation() -> bool:
    """Only allowed entity types are accepted."""
    print("\n[Test 5] EntityType controlled vocabulary")
    try:
        valid_types = [e.value for e in EntityType]
        for etype in valid_types:
            e = Entity(name="Test", entity_type=etype)
            assert e.entity_type == etype
        print(f"  ✅ All {len(valid_types)} entity types valid: {valid_types}")

        # Invalid types should raise a validation error
        try:
            Entity(name="Test", entity_type="INVALID_TYPE")
            print("  ❌ Should have rejected invalid entity type")
            return False
        except (ValueError, Exception):
            print("  ✅ Invalid entity type correctly rejected")

        return True
    except Exception as exc:
        print(f"  ❌ Entity type validation test failed: {exc}")
        return False


def test_relation_type_validation() -> bool:
    """Only allowed relation types are accepted."""
    print("\n[Test 6] RelationType controlled vocabulary")
    try:
        valid_types = [r.value for r in RelationType]
        for rtype in valid_types:
            r = Relation(source="A", target="B", relation_type=rtype)
            assert r.relation_type == rtype
        print(f"  ✅ All {len(valid_types)} relation types valid")

        try:
            Relation(source="A", target="B", relation_type="UNKNOWN_REL")
            print("  ❌ Should have rejected invalid relation type")
            return False
        except (ValueError, Exception):
            print("  ✅ Invalid relation type correctly rejected")

        return True
    except Exception as exc:
        print(f"  ❌ Relation type validation test failed: {exc}")
        return False


# ===========================================================================
# Runner
# ===========================================================================

def main() -> int:
    print("=" * 60)
    print("  EL'druin Knowledge Layer – Test Suite")
    print("=" * 60)

    tests = [
        ("Entity model", test_entity_model),
        ("Relation model", test_relation_model),
        ("Triple model", test_triple_model),
        ("KGExtractor stub mode", test_extractor_stub_mode),
        ("KGExtractor empty input", test_extractor_empty_input),
        ("KGExtractor batch", test_extractor_batch),
        ("GraphBuilder NetworkX", test_graph_builder_networkx),
        ("GraphBuilder query_neighbors", test_graph_builder_query_neighbors),
        ("GraphBuilder Kuzu", test_graph_builder_kuzu),
        ("Cache hit/miss", test_cache_hit_miss),
        ("Cache normalisation", test_cache_normalisation),
        ("Cache empty input", test_cache_empty_input),
        ("Cache clear", test_cache_clear),
        ("EntityType vocabulary", test_entity_type_validation),
        ("RelationType vocabulary", test_relation_type_validation),
    ]

    passed = 0
    failed = 0
    start = time.time()

    for name, fn in tests:
        try:
            ok = fn()
        except Exception as exc:
            print(f"  ❌ {name} raised exception: {exc}")
            ok = False
        if ok:
            passed += 1
        else:
            failed += 1

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(
        f"  Results: {passed}/{len(tests)} passed, {failed} failed "
        f"({elapsed:.2f}s)"
    )
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
