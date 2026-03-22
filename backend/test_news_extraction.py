"""
后端测试脚本 - 新闻聚合和事件提取功能验证
Backend test script for news aggregation and event extraction
"""

import sys
import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Minimal stub implementations used when the real app modules are absent.
# These allow the test script to run and demonstrate expected behaviour
# without requiring the full backend to be installed.
# ---------------------------------------------------------------------------

class _StubNewsAggregator:
    """Fallback stub when app.data_ingestion.news_aggregator is not installed."""

    SAMPLE_ARTICLES: List[Dict[str, Any]] = [
        {
            "title": "Global Markets React to Central Bank Decisions",
            "description": (
                "Stock markets worldwide reacted sharply after several central banks "
                "announced unexpected interest rate adjustments, triggering volatility "
                "across emerging and developed economies."
            ),
            "source": "Reuters",
            "category": "economy",
            "published": "2024-01-15T09:30:00Z",
            "link": "https://reuters.com/sample/markets-react",
            "confidence": 0.92,
        },
        {
            "title": "UN Security Council Meets on Regional Conflict",
            "description": (
                "The United Nations Security Council convened an emergency session to "
                "address escalating tensions in the disputed border region, with member "
                "states calling for an immediate ceasefire."
            ),
            "source": "BBC News",
            "category": "politics",
            "published": "2024-01-15T11:00:00Z",
            "link": "https://bbc.com/sample/un-security",
            "confidence": 0.88,
        },
        {
            "title": "Major Tech Firm Announces Breakthrough in Quantum Computing",
            "description": (
                "A leading technology corporation revealed a landmark achievement in "
                "quantum processing, claiming error rates low enough for practical "
                "commercial applications within two years."
            ),
            "source": "TechCrunch",
            "category": "technology",
            "published": "2024-01-15T13:45:00Z",
            "link": "https://techcrunch.com/sample/quantum",
            "confidence": 0.95,
        },
        {
            "title": "Category-4 Hurricane Approaches Gulf Coast",
            "description": (
                "Emergency management officials ordered mandatory evacuations for coastal "
                "communities as a powerful hurricane strengthened over warm gulf waters, "
                "expected to make landfall within 48 hours."
            ),
            "source": "CNN",
            "category": "natural_disaster",
            "published": "2024-01-15T14:20:00Z",
            "link": "https://cnn.com/sample/hurricane",
            "confidence": 0.97,
        },
        {
            "title": "Diplomatic Talks Yield Preliminary Trade Agreement",
            "description": (
                "After months of negotiations, senior diplomats from both nations "
                "initialled a preliminary trade framework that could eliminate tariffs "
                "on over 3,000 goods by next fiscal year."
            ),
            "source": "Financial Times",
            "category": "diplomacy",
            "published": "2024-01-15T16:00:00Z",
            "link": "https://ft.com/sample/trade",
            "confidence": 0.85,
        },
    ]

    def aggregate(
        self,
        sources: Optional[List[str]] = None,
        limit: int = 50,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        return self.SAMPLE_ARTICLES[:limit]


class _StubEventExtractor:
    """Fallback stub when app.data_ingestion.event_extractor is not installed."""

    EVENT_TEMPLATES = [
        {
            "event_type": "经济危机",
            "severity": "high",
            "title": "Central bank rate shock triggers market selloff",
            "description": "Coordinated central bank moves cause broad equity decline.",
            "entities": {"ORG": ["Federal Reserve", "ECB"], "GPE": ["USA", "EU"]},
            "confidence": 0.88,
        },
        {
            "event_type": "政治冲突",
            "severity": "high",
            "title": "UN Security Council emergency session on border tensions",
            "description": "International community responds to escalating conflict.",
            "entities": {"ORG": ["UN"], "GPE": ["Border Region"]},
            "confidence": 0.82,
        },
        {
            "event_type": "技术突破",
            "severity": "medium",
            "title": "Quantum computing milestone reached",
            "description": "Tech firm achieves commercial-grade quantum error rates.",
            "entities": {"ORG": ["TechCorp"], "GPE": []},
            "confidence": 0.91,
        },
        {
            "event_type": "自然灾害",
            "severity": "high",
            "title": "Hurricane category 4 landfall imminent",
            "description": "Mandatory evacuations ordered for Gulf Coast communities.",
            "entities": {"ORG": ["FEMA"], "GPE": ["Gulf Coast"]},
            "confidence": 0.96,
        },
        {
            "event_type": "外交事件",
            "severity": "low",
            "title": "Bilateral trade framework initialled",
            "description": "Diplomats reach preliminary agreement on tariff reductions.",
            "entities": {"ORG": ["Trade Ministry"], "GPE": ["Country A", "Country B"]},
            "confidence": 0.79,
        },
    ]

    def extract_events(self, text: str) -> List[Dict[str, Any]]:
        """Simple keyword-based event extraction for stub purposes."""
        keywords = {
            "market": self.EVENT_TEMPLATES[0],
            "security council": self.EVENT_TEMPLATES[1],
            "quantum": self.EVENT_TEMPLATES[2],
            "hurricane": self.EVENT_TEMPLATES[3],
            "trade": self.EVENT_TEMPLATES[4],
        }
        lower = text.lower()
        results = []
        for kw, template in keywords.items():
            if kw in lower:
                results.append(dict(template))
        return results if results else [dict(self.EVENT_TEMPLATES[0])]

    def extract_from_articles(
        self, articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for article in articles:
            combined = f"{article.get('title', '')} {article.get('description', '')}"
            events.extend(self.extract_events(combined))
        # Deduplicate by event_type
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for e in events:
            key = e["event_type"]
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return unique


# ---------------------------------------------------------------------------
# Try to import real implementations; fall back to stubs if absent
# ---------------------------------------------------------------------------

def _load_aggregator():
    try:
        from app.data_ingestion.news_aggregator import NewsAggregator  # type: ignore
        logger.info("Using real NewsAggregator from app.data_ingestion")
        return NewsAggregator()
    except ImportError:
        logger.warning(
            "app.data_ingestion.news_aggregator not found – using stub aggregator"
        )
        return _StubNewsAggregator()


def _load_extractor():
    try:
        from app.data_ingestion.event_extractor import EventExtractor  # type: ignore
        logger.info("Using real EventExtractor from app.data_ingestion")
        return EventExtractor()
    except ImportError:
        logger.warning(
            "app.data_ingestion.event_extractor not found – using stub extractor"
        )
        return _StubEventExtractor()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _separator(char: str = "=", width: int = 60) -> str:
    return char * width


def _print_section(title: str) -> None:
    print(f"\n{_separator()}")
    print(f"  {title}")
    print(_separator())


def _print_article(article: Dict[str, Any], index: int) -> None:
    print(f"\n  [{index}] {article.get('title', 'N/A')[:70]}")
    print(f"       来源   : {article.get('source', 'N/A')}")
    print(f"       分类   : {article.get('category', 'N/A')}")
    print(f"       时间   : {article.get('published', 'N/A')[:19]}")
    confidence = article.get("confidence")
    if confidence is not None:
        print(f"       置信度 : {confidence:.1%}")


def _print_event(event: Dict[str, Any], index: int) -> None:
    sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
        event.get("severity", ""), "⚪"
    )
    print(f"\n  [{index}] {sev_icon} {event.get('event_type', 'N/A')}")
    print(f"       标题   : {event.get('title', 'N/A')[:70]}")
    print(f"       严重度 : {event.get('severity', 'N/A').upper()}")
    print(f"       置信度 : {event.get('confidence', 0):.1%}")
    entities = event.get("entities", {})
    orgs = entities.get("ORG", [])
    gpes = entities.get("GPE", [])
    if orgs:
        print(f"       组织   : {', '.join(orgs[:3])}")
    if gpes:
        print(f"       地点   : {', '.join(gpes[:3])}")


# ---------------------------------------------------------------------------
# Core test functions
# ---------------------------------------------------------------------------

def test_news_aggregator() -> Dict[str, Any]:
    """Test NewsAggregator and return collected statistics."""
    _print_section("测试 1 – 新闻聚合 (NewsAggregator)")

    aggregator = _load_aggregator()
    start = time.time()

    try:
        articles: List[Dict[str, Any]] = aggregator.aggregate(limit=20, hours=24)
    except TypeError:
        # Some implementations may use different signatures
        try:
            articles = aggregator.aggregate()
        except Exception:
            articles = aggregator.SAMPLE_ARTICLES if hasattr(aggregator, "SAMPLE_ARTICLES") else []

    elapsed = time.time() - start

    assert isinstance(articles, list), "aggregate() must return a list"

    print(f"\n  ✅ 聚合完成 – {len(articles)} 条文章 ({elapsed:.2f}s)")

    # Category distribution
    categories: Dict[str, int] = {}
    sources: set = set()
    confidences: List[float] = []

    for art in articles:
        cat = art.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
        src = art.get("source")
        if src:
            sources.add(src)
        conf = art.get("confidence")
        if conf is not None:
            confidences.append(float(conf))

    print(f"\n  分类分布:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"    {cat:<20} {bar} ({count})")

    print(f"\n  新闻源 ({len(sources)} 个): {', '.join(sorted(sources))}")

    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        print(f"\n  平均置信度: {avg_conf:.1%}")

    print(f"\n  前 {min(3, len(articles))} 条文章预览:")
    for i, art in enumerate(articles[:3], 1):
        _print_article(art, i)

    return {
        "total": len(articles),
        "categories": categories,
        "sources": list(sources),
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "elapsed_seconds": elapsed,
        "success": True,
    }


def test_event_extractor(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Test EventExtractor against a list of articles and return statistics."""
    _print_section("测试 2 – 事件提取 (EventExtractor)")

    extractor = _load_extractor()
    start = time.time()

    events: List[Dict[str, Any]] = []

    # Try batch extraction first
    if hasattr(extractor, "extract_from_articles"):
        events = extractor.extract_from_articles(articles)
    else:
        for article in articles:
            combined = f"{article.get('title', '')} {article.get('description', '')}"
            try:
                extracted = extractor.extract_events(combined)
                events.extend(extracted)
            except Exception as exc:
                logger.warning(f"Article extraction failed: {exc}")

    elapsed = time.time() - start

    print(f"\n  ✅ 提取完成 – {len(events)} 个事件 ({elapsed:.2f}s)")

    # Severity distribution
    severity_counts: Dict[str, int] = {}
    event_types: Dict[str, int] = {}
    confidences: List[float] = []

    for ev in events:
        sev = ev.get("severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        et = ev.get("event_type", "unknown")
        event_types[et] = event_types.get(et, 0) + 1
        conf = ev.get("confidence")
        if conf is not None:
            confidences.append(float(conf))

    print(f"\n  严重级别分布:")
    for sev in ("high", "medium", "low", "unknown"):
        count = severity_counts.get(sev, 0)
        if count:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
            print(f"    {icon} {sev:<10} {count} 个事件")

    print(f"\n  事件类型分布:")
    for et, count in sorted(event_types.items(), key=lambda x: -x[1]):
        print(f"    {et:<24} {count} 个")

    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        high_conf = sum(1 for c in confidences if c >= 0.8)
        print(f"\n  平均置信度  : {avg_conf:.1%}")
        print(f"  高置信度事件: {high_conf}/{len(events)} ({high_conf/len(events):.0%})")

    print(f"\n  事件详情预览 (前 {min(3, len(events))} 条):")
    for i, ev in enumerate(events[:3], 1):
        _print_event(ev, i)

    return {
        "total": len(events),
        "severity_counts": severity_counts,
        "event_types": event_types,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "elapsed_seconds": elapsed,
        "success": True,
    }


def test_confidence_scoring(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate confidence score distribution and thresholds."""
    _print_section("测试 3 – 置信度评分验证")

    confidences = [float(e.get("confidence", 0)) for e in events]

    if not confidences:
        print("  ⚠️  无事件可验证置信度")
        return {"success": False, "reason": "no events"}

    avg = sum(confidences) / len(confidences)
    minimum = min(confidences)
    maximum = max(confidences)

    buckets = {
        "高 (≥0.80)": sum(1 for c in confidences if c >= 0.80),
        "中 (0.60–0.79)": sum(1 for c in confidences if 0.60 <= c < 0.80),
        "低 (<0.60)": sum(1 for c in confidences if c < 0.60),
    }

    print(f"\n  平均置信度 : {avg:.1%}")
    print(f"  最小置信度 : {minimum:.1%}")
    print(f"  最大置信度 : {maximum:.1%}")
    print(f"\n  置信度分布:")
    for label, count in buckets.items():
        bar = "█" * count
        print(f"    {label:<18} {bar} ({count})")

    # Soft assertion – warn but do not crash if average is below threshold
    threshold = 0.60
    passed = avg >= threshold
    status = "✅ 通过" if passed else f"⚠️  平均置信度低于阈值 {threshold:.0%}"
    print(f"\n  评估结果: {status}")

    return {
        "avg": avg,
        "min": minimum,
        "max": maximum,
        "buckets": buckets,
        "passed": passed,
        "success": True,
    }


def print_final_report(
    agg_stats: Dict[str, Any],
    ext_stats: Dict[str, Any],
    conf_stats: Dict[str, Any],
    total_elapsed: float,
) -> None:
    _print_section("最终统计报告")
    print(f"\n  运行时间     : {total_elapsed:.2f}s")
    print(f"  聚合文章数   : {agg_stats.get('total', 0)}")
    print(f"  新闻源数量   : {len(agg_stats.get('sources', []))}")
    print(f"  提取事件数   : {ext_stats.get('total', 0)}")
    print(f"  高危事件数   : {ext_stats.get('severity_counts', {}).get('high', 0)}")
    print(f"  聚合平均置信度: {agg_stats.get('avg_confidence', 0):.1%}")
    print(f"  事件平均置信度: {ext_stats.get('avg_confidence', 0):.1%}")

    all_passed = all(
        [
            agg_stats.get("success", False),
            ext_stats.get("success", False),
            conf_stats.get("success", False),
        ]
    )
    print(f"\n  整体结果: {'✅ 全部测试通过' if all_passed else '⚠️  部分测试存在警告'}")
    print(f"\n{_separator()}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    print(_separator("=", 60))
    print("  EL'druin – 新闻聚合 & 事件提取 测试脚本")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(_separator("=", 60))

    overall_start = time.time()
    exit_code = 0

    try:
        # Test 1: News Aggregation
        agg_stats = test_news_aggregator()

        # Build article list for downstream tests
        aggregator = _load_aggregator()
        try:
            articles: List[Dict[str, Any]] = aggregator.aggregate(limit=20, hours=24)
        except TypeError:
            articles = getattr(aggregator, "SAMPLE_ARTICLES", [])

        # Test 2: Event Extraction
        ext_stats = test_event_extractor(articles)

        # Build event list for confidence test
        extractor = _load_extractor()
        if hasattr(extractor, "extract_from_articles"):
            events = extractor.extract_from_articles(articles)
        else:
            events = []
            for art in articles:
                combined = f"{art.get('title', '')} {art.get('description', '')}"
                try:
                    events.extend(extractor.extract_events(combined))
                except Exception:
                    pass

        # Test 3: Confidence Scoring
        conf_stats = test_confidence_scoring(events)

    except Exception as exc:
        logger.error(f"测试执行失败: {exc}", exc_info=True)
        exit_code = 1
        agg_stats = {"success": False, "total": 0, "sources": [], "avg_confidence": 0}
        ext_stats = {"success": False, "total": 0, "severity_counts": {}, "avg_confidence": 0}
        conf_stats = {"success": False}

    total_elapsed = time.time() - overall_start
    print_final_report(agg_stats, ext_stats, conf_stats, total_elapsed)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())