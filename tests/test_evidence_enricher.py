"""
tests/test_evidence_enricher.py
=================================
Unit tests for the Deep Ontology Analysis evidence enrichment pipeline.

All HTTP calls are mocked – no real network requests are made.

Coverage:
- DeepConfig.from_dict
- _enrich_from_local_meta
- _enrich_from_source_url (with mocked urllib)
- _web_search_snippets (with mocked urllib)
- _enrich_from_web_search
- EnrichmentResult.to_dict
- EvidenceEnricher.enrich – level 0, 1, 2, 3
- Cache hit
- Graceful failure (HTTP error)
- Empty missing_before → no-op
"""

from __future__ import annotations

import json
import sys
import os
import io
import unittest
from unittest.mock import patch, MagicMock
from http.client import HTTPMessage

# Make backend importable from the tests directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from intelligence.evidence_enricher import (
    DeepConfig,
    EnrichmentResult,
    ProvenanceEntry,
    EvidenceEnricher,
    _EnrichmentCache,
    _enrich_from_local_meta,
    _enrich_from_source_url,
    _web_search_snippets,
    _enrich_from_web_search,
    _build_enriched_context,
    enrich_missing_anchors,
)


# ===========================================================================
# Helpers
# ===========================================================================

_ALL_MISSING = [
    "specific_date",
    "named_institution_or_official_source",
    "official_document_or_url_reference",
]


def _make_http_response(body: str, content_type: str = "text/html; charset=utf-8"):
    """Build a mock urllib response context-manager."""
    encoded = body.encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = encoded
    mock_resp.headers = {"Content-Type": content_type}
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_ddg_response(abstract_text: str = "", abstract_url: str = "", related: list | None = None):
    """Build a mock DuckDuckGo JSON response."""
    data = {
        "AbstractText": abstract_text,
        "AbstractURL": abstract_url,
        "Heading": "Test Heading",
        "RelatedTopics": related or [],
    }
    return _make_http_response(json.dumps(data), content_type="application/json")


# ===========================================================================
# A. DeepConfig
# ===========================================================================

class TestDeepConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = DeepConfig()
        self.assertEqual(cfg.level, 0)
        self.assertEqual(cfg.max_sources, 3)

    def test_from_dict_partial(self):
        cfg = DeepConfig.from_dict({"level": 2, "max_sources": 5})
        self.assertEqual(cfg.level, 2)
        self.assertEqual(cfg.max_sources, 5)
        self.assertEqual(cfg.timeout_seconds, 20)  # default

    def test_from_dict_empty(self):
        cfg = DeepConfig.from_dict({})
        self.assertEqual(cfg.level, 0)

    def test_from_dict_none(self):
        # from_dict should handle None gracefully and return defaults
        cfg = DeepConfig.from_dict({})
        self.assertEqual(cfg.level, 0)


# ===========================================================================
# B. Local metadata enrichment
# ===========================================================================

class TestLocalMetaEnrichment(unittest.TestCase):
    def _run(self, missing, meta):
        prov: list = []
        remaining = _enrich_from_local_meta(missing, meta, prov)
        return remaining, prov

    def test_fills_all_from_meta(self):
        meta = {
            "published_at": "2024-03-15",
            "source": "Reuters",
            "url": "https://reuters.com/article/123",
        }
        remaining, prov = self._run(list(_ALL_MISSING), meta)
        self.assertEqual(remaining, [])
        self.assertEqual(len(prov), 3)
        anchor_types = {p.anchor_type for p in prov}
        self.assertIn("specific_date", anchor_types)
        self.assertIn("named_institution_or_official_source", anchor_types)
        self.assertIn("official_document_or_url_reference", anchor_types)

    def test_fills_only_date(self):
        meta = {"published_at": "2024-01-01", "source": "", "url": ""}
        remaining, prov = self._run(["specific_date", "named_institution_or_official_source"], meta)
        self.assertIn("named_institution_or_official_source", remaining)
        self.assertNotIn("specific_date", remaining)
        self.assertEqual(len(prov), 1)

    def test_empty_meta_leaves_all_missing(self):
        remaining, prov = self._run(list(_ALL_MISSING), {})
        self.assertEqual(remaining, list(_ALL_MISSING))
        self.assertEqual(prov, [])

    def test_high_confidence_for_known_meta(self):
        meta = {"published_at": "2024-06-10", "source": "BBC", "url": "https://bbc.com/news/1"}
        _, prov = self._run(list(_ALL_MISSING), meta)
        for p in prov:
            self.assertGreaterEqual(p.confidence, 0.80)


# ===========================================================================
# C. Source URL fetch enrichment
# ===========================================================================

class TestSourceUrlEnrichment(unittest.TestCase):
    _RICH_PAGE = (
        "Published: 15 March 2024. "
        "The European Commission announced... "
        "See the full report at https://ec.europa.eu/report/456"
    )

    @patch("urllib.request.urlopen")
    def test_fills_from_page(self, mock_urlopen):
        mock_urlopen.return_value = _make_http_response(self._RICH_PAGE)
        prov: list = []
        remaining, cnt = _enrich_from_source_url(
            list(_ALL_MISSING), "https://example.com/news", prov
        )
        self.assertEqual(cnt, 1)
        self.assertNotIn("specific_date", remaining)
        self.assertNotIn("named_institution_or_official_source", remaining)
        anchor_types = {p.anchor_type for p in prov}
        self.assertIn("specific_date", anchor_types)
        self.assertIn("named_institution_or_official_source", anchor_types)

    @patch("urllib.request.urlopen", side_effect=OSError("connection refused"))
    def test_returns_unchanged_on_error(self, _mock):
        prov: list = []
        remaining, cnt = _enrich_from_source_url(
            list(_ALL_MISSING), "https://bad-host.example", prov
        )
        self.assertEqual(remaining, list(_ALL_MISSING))
        self.assertEqual(cnt, 0)
        self.assertEqual(prov, [])

    @patch("urllib.request.urlopen")
    def test_non_text_content_type_skipped(self, mock_urlopen):
        mock_urlopen.return_value = _make_http_response(b"binary".decode(), "application/pdf")
        prov: list = []
        remaining, cnt = _enrich_from_source_url(
            list(_ALL_MISSING), "https://example.com/doc.pdf", prov
        )
        self.assertEqual(remaining, list(_ALL_MISSING))
        self.assertEqual(cnt, 0)


# ===========================================================================
# D. Web search enrichment
# ===========================================================================

class TestWebSearchSnippets(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_returns_abstract(self, mock_urlopen):
        mock_urlopen.return_value = _make_ddg_response(
            abstract_text="On 10 April 2024 the US Treasury sanctioned...",
            abstract_url="https://treasury.gov/press/2024/04/10",
        )
        results = _web_search_snippets("tariffs sanctions 2024")
        self.assertTrue(len(results) >= 1)
        self.assertIn("2024", results[0]["snippet"])

    @patch("urllib.request.urlopen")
    def test_returns_related_topics(self, mock_urlopen):
        mock_urlopen.return_value = _make_ddg_response(
            related=[
                {
                    "Text": "On 5 January 2024, IMF released a report on tariffs.",
                    "FirstURL": "https://imf.org/report/tariffs",
                    "Name": "IMF Tariff Report",
                },
                {
                    "Text": "Additional context about trade wars.",
                    "FirstURL": "https://example.com/trade",
                    "Name": "Trade Wars",
                },
            ]
        )
        results = _web_search_snippets("tariffs IMF 2024", max_results=2)
        self.assertLessEqual(len(results), 2)

    @patch("urllib.request.urlopen", side_effect=OSError("DNS failure"))
    def test_returns_empty_on_error(self, _mock):
        results = _web_search_snippets("anything")
        self.assertEqual(results, [])


class TestWebSearchEnrichment(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_fills_date_from_snippet(self, mock_urlopen):
        mock_urlopen.return_value = _make_ddg_response(
            abstract_text=(
                "On 20 February 2024, the US Congress approved new tariffs "
                "affecting American consumers. https://congress.gov/tariffs/2024"
            ),
            abstract_url="https://congress.gov/tariffs/2024",
        )
        prov: list = []
        remaining, searched, used = _enrich_from_web_search(
            list(_ALL_MISSING), "tariff impact Americans 2024", prov, max_sources=3
        )
        self.assertTrue(searched)
        self.assertNotIn("specific_date", remaining)
        anchor_types = {p.anchor_type for p in prov}
        self.assertIn("specific_date", anchor_types)

    @patch("urllib.request.urlopen", side_effect=OSError("timeout"))
    def test_returns_all_missing_on_search_failure(self, _mock):
        prov: list = []
        remaining, searched, used = _enrich_from_web_search(
            list(_ALL_MISSING), "some query", prov
        )
        # searched=True because we attempted; all still missing
        self.assertEqual(remaining, list(_ALL_MISSING))
        self.assertEqual(prov, [])
        self.assertEqual(used, 0)


# ===========================================================================
# E. EvidenceEnricher end-to-end
# ===========================================================================

class TestEvidenceEnricher(unittest.TestCase):
    def _fresh_enricher(self) -> EvidenceEnricher:
        """Return an enricher with a fresh empty cache."""
        cache = _EnrichmentCache(ttl=3600)
        return EvidenceEnricher(cache=cache)

    def test_level_0_returns_disabled(self):
        enricher = self._fresh_enricher()
        result = enricher.enrich(
            text="Some news text",
            missing_before=list(_ALL_MISSING),
            deep_config=DeepConfig(level=0),
        )
        self.assertTrue(result.enabled)
        self.assertEqual(result.missing_after, list(_ALL_MISSING))
        self.assertEqual(result.provenance, [])

    def test_empty_missing_before_returns_immediately(self):
        enricher = self._fresh_enricher()
        result = enricher.enrich(
            text="news",
            missing_before=[],
            deep_config=DeepConfig(level=3),
        )
        self.assertEqual(result.missing_after, [])
        self.assertEqual(result.provenance, [])

    def test_level_1_fills_from_local_meta(self):
        enricher = self._fresh_enricher()
        result = enricher.enrich(
            text="tariffs news",
            missing_before=list(_ALL_MISSING),
            deep_config=DeepConfig(level=1),
            local_meta={
                "published_at": "2024-04-01",
                "source": "Reuters",
                "url": "https://reuters.com/article/1",
            },
        )
        self.assertEqual(result.missing_after, [])
        self.assertEqual(len(result.provenance), 3)
        self.assertFalse(result.cache_hit)

    def test_level_1_cache_hit(self):
        enricher = self._fresh_enricher()
        meta = {
            "published_at": "2024-04-01",
            "source": "AP",
            "url": "https://apnews.com/1",
        }
        # First call – not cached
        r1 = enricher.enrich(
            text="tariffs cost Americans",
            missing_before=list(_ALL_MISSING),
            deep_config=DeepConfig(level=1),
            local_meta=meta,
        )
        self.assertFalse(r1.cache_hit)

        # Second call – should hit cache
        r2 = enricher.enrich(
            text="tariffs cost Americans",
            missing_before=list(_ALL_MISSING),
            deep_config=DeepConfig(level=1),
            local_meta=meta,
        )
        self.assertTrue(r2.cache_hit)
        self.assertEqual(r2.missing_after, r1.missing_after)

    @patch("urllib.request.urlopen")
    def test_level_2_fetches_source_url(self, mock_urlopen):
        page_body = (
            "Published: 01 April 2024. "
            "The IMF released a statement on tariffs. "
            "See https://imf.org/statement/2024 for details."
        )
        mock_urlopen.return_value = _make_http_response(page_body)

        enricher = self._fresh_enricher()
        result = enricher.enrich(
            text="How tariffs cost Americans",
            missing_before=list(_ALL_MISSING),
            deep_config=DeepConfig(level=2),
            source_url="https://reuters.com/tariffs",
        )
        self.assertNotIn("specific_date", result.missing_after)
        self.assertNotIn("named_institution_or_official_source", result.missing_after)
        self.assertGreater(result.limits["fetched_urls"], 0)
        self.assertFalse(result.limits["searched"])

    @patch("urllib.request.urlopen")
    def test_level_3_uses_web_search(self, mock_urlopen):
        # level 1: no local meta → nothing filled
        # level 2: no source_url → nothing filled
        # level 3: web search should fill something
        mock_urlopen.return_value = _make_ddg_response(
            abstract_text=(
                "On 2 April 2024 the US Congress passed new tariff legislation. "
                "The Federal Reserve warned about economic impact. "
                "https://congress.gov/tariffs"
            ),
            abstract_url="https://congress.gov/tariffs",
        )

        enricher = self._fresh_enricher()
        result = enricher.enrich(
            text="How tariffs cost Americans",
            missing_before=list(_ALL_MISSING),
            deep_config=DeepConfig(level=3),
        )
        self.assertTrue(result.limits["searched"])
        self.assertNotIn("specific_date", result.missing_after)

    @patch("urllib.request.urlopen", side_effect=OSError("network failure"))
    def test_graceful_failure_level_2(self, _mock):
        """Level-2 fetch failure should not raise; remaining anchors = missing_before."""
        enricher = self._fresh_enricher()
        result = enricher.enrich(
            text="news",
            missing_before=["specific_date"],
            deep_config=DeepConfig(level=2, timeout_seconds=1),
            source_url="https://bad.example.com",
        )
        # Should not raise and should return missing_after = ["specific_date"]
        self.assertIn("specific_date", result.missing_after)
        self.assertIsNone(result.error)  # error is None; graceful fallback inside _enrich_from_source_url

    def test_to_dict_serialisable(self):
        enricher = self._fresh_enricher()
        result = enricher.enrich(
            text="some news",
            missing_before=["specific_date"],
            deep_config=DeepConfig(level=1),
            local_meta={"published_at": "2024-01-01", "source": "AP", "url": ""},
        )
        d = result.to_dict()
        # Must be JSON-serialisable
        serialised = json.dumps(d)
        self.assertIn("provenance", serialised)
        self.assertIn("missing_before", serialised)
        self.assertIn("limits", serialised)


# ===========================================================================
# F. Context builder
# ===========================================================================

class TestBuildEnrichedContext(unittest.TestCase):
    def test_empty_provenance_returns_empty_string(self):
        ctx = _build_enriched_context([])
        self.assertEqual(ctx, "")

    def test_includes_anchor_type_and_snippet(self):
        prov = [
            ProvenanceEntry(
                anchor_type="specific_date",
                source_url="https://example.com",
                title="Example",
                snippet="15 March 2024",
                fetched_at="2024-03-15T00:00:00Z",
                confidence=0.95,
            )
        ]
        ctx = _build_enriched_context(prov)
        self.assertIn("specific_date", ctx)
        self.assertIn("15 March 2024", ctx)
        self.assertIn("Evidence Anchors", ctx)


# ===========================================================================
# G. Module-level convenience function
# ===========================================================================

class TestEnrichMissingAnchors(unittest.TestCase):
    def test_convenience_function_level_1(self):
        result = enrich_missing_anchors(
            text="news text",
            missing_before=["specific_date"],
            deep_config=DeepConfig(level=1),
            local_meta={"published_at": "2024-07-04"},
        )
        self.assertIsInstance(result, EnrichmentResult)
        self.assertNotIn("specific_date", result.missing_after)


if __name__ == "__main__":
    unittest.main()
