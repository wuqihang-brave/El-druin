"""
单元测试：秩序评论家（OrderCritic）

测试范围：
1. 琐碎信息（娱乐八卦）能被正确过滤
2. 结构性信息（技术突破、地缘政治）能被保留
3. OrderedTriple 数据模型的约束逻辑
4. filter_triples 的模式（strict / balanced）和阈值逻辑
5. 缓存机制正确命中
6. 兜底评估逻辑（无 API key 时）
"""

from __future__ import annotations

import sys
import os

# 将 backend 目录加入 Python 路径，以便直接导入 knowledge_layer
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

import pytest
from unittest.mock import MagicMock, patch

from knowledge_layer.order_models import OrderedTriple
from knowledge_layer.order_critic import OrderCritic, _MODE_THRESHOLDS


# ---------------------------------------------------------------------------
# OrderedTriple 数据模型测试
# ---------------------------------------------------------------------------

class TestOrderedTriple:
    def test_basic_creation(self):
        t = OrderedTriple(subject="OpenAI", relation="releases", object="GPT-5")
        assert t.subject == "OpenAI"
        assert t.relation == "releases"
        assert t.object == "GPT-5"
        assert t.order_score == 0.0
        assert t.category == "unknown"

    def test_score_clamping_above_100(self):
        t = OrderedTriple(subject="A", relation="B", object="C", order_score=150.0)
        assert t.order_score == 100.0

    def test_score_clamping_below_0(self):
        t = OrderedTriple(subject="A", relation="B", object="C", order_score=-10.0)
        assert t.order_score == 0.0

    def test_confidence_clamping(self):
        t = OrderedTriple(subject="A", relation="B", object="C", confidence=2.5)
        assert t.confidence == 1.0
        t2 = OrderedTriple(subject="A", relation="B", object="C", confidence=-0.1)
        assert t2.confidence == 0.0

    def test_is_ordered_true(self):
        t = OrderedTriple(subject="A", relation="B", object="C", order_score=75.0)
        assert t.is_ordered is True

    def test_is_ordered_false(self):
        t = OrderedTriple(subject="A", relation="B", object="C", order_score=49.9)
        assert t.is_ordered is False

    def test_to_dict_keys(self):
        t = OrderedTriple(
            subject="Federal Reserve",
            relation="raises",
            object="interest rates",
            order_score=85.0,
            reasoning="Central bank policy has long-term structural impact.",
            category="institution",
            confidence=0.9,
        )
        d = t.to_dict()
        assert set(d.keys()) == {"subject", "relation", "object", "order_score", "reasoning", "category", "confidence"}
        assert d["order_score"] == 85.0
        assert d["category"] == "institution"


# ---------------------------------------------------------------------------
# OrderCritic 模式阈值测试
# ---------------------------------------------------------------------------

class TestModeThresholds:
    def test_strict_mode_threshold(self):
        assert _MODE_THRESHOLDS["strict"] == 80.0

    def test_balanced_mode_threshold(self):
        assert _MODE_THRESHOLDS["balanced"] == 50.0


# ---------------------------------------------------------------------------
# OrderCritic 兜底评估测试（无 API key）
# ---------------------------------------------------------------------------

class TestFallbackEvaluation:
    """当 GROQ_API_KEY 未配置时，应使用规则兜底逻辑。"""

    def setup_method(self):
        # 确保没有 API key
        self.critic = OrderCritic(api_key=None)

    def test_trivial_triple_gets_low_score(self):
        """娱乐八卦三元组应获得低评分（< 50）。"""
        result = self.critic.evaluate_triple(
            "Taylor Swift", "attends", "Grammy party gossip"
        )
        assert isinstance(result, OrderedTriple)
        assert result.order_score < 50.0

    def test_technology_triple_gets_decent_score(self):
        """含技术突破关键词的三元组应获得较高评分（>= 50）。"""
        result = self.critic.evaluate_triple(
            "OpenAI", "achieves", "quantum breakthrough"
        )
        assert result.order_score >= 50.0

    def test_geopolitics_triple_preserved(self):
        """含地缘政治关键词的三元组应获得较高评分。"""
        result = self.critic.evaluate_triple(
            "USA", "signs", "trade agreement with EU"
        )
        assert result.order_score >= 50.0

    def test_celebrity_gossip_filtered(self):
        """明星八卦应被过滤（低分）。"""
        result = self.critic.evaluate_triple(
            "celebrity", "gossip", "selfie award"
        )
        assert result.order_score < 50.0

    def test_result_has_required_fields(self):
        """兜底评估结果应包含所有必要字段。"""
        result = self.critic.evaluate_triple("A", "B", "C")
        assert hasattr(result, "order_score")
        assert hasattr(result, "reasoning")
        assert hasattr(result, "category")
        assert hasattr(result, "confidence")
        assert 0.0 <= result.order_score <= 100.0
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# filter_triples 逻辑测试
# ---------------------------------------------------------------------------

class TestFilterTriples:
    def setup_method(self):
        self.critic = OrderCritic(api_key=None)

    def test_empty_input_returns_empty(self):
        result = self.critic.filter_triples([])
        assert result == []

    def test_balanced_mode_filters_low_scores(self):
        """balanced 模式（阈值 50）应过滤琐碎信息。"""
        triples = [
            {"subject": "Taylor Swift", "relation": "gossip", "object": "celebrity party"},
            {"subject": "USA", "relation": "signs", "object": "nuclear agreement"},
        ]
        result = self.critic.filter_triples(triples, mode="balanced")
        # 只有高价值三元组应保留
        assert all(t.order_score >= 50.0 for t in result)

    def test_strict_mode_higher_threshold(self):
        """strict 模式（阈值 80）应只保留高评分三元组。"""
        # 用 mock 打桩：对量子突破返回 85 分，对协议返回 65 分
        with patch.object(self.critic, "_fallback_evaluation") as mock_eval:
            def side_effect(subject: str, relation: str, obj: str) -> OrderedTriple:
                if "quantum" in obj:
                    return OrderedTriple(subject, relation, obj, order_score=85.0, confidence=0.9)
                return OrderedTriple(subject, relation, obj, order_score=65.0, confidence=0.7)
            mock_eval.side_effect = side_effect

            triples = [
                {"subject": "IBM", "relation": "achieves", "object": "quantum computing milestone"},
                {"subject": "EU", "relation": "signs", "object": "trade deal"},
            ]
            result = self.critic.filter_triples(triples, mode="strict")
            assert len(result) == 1
            assert result[0].subject == "IBM"

    def test_result_sorted_by_score_descending(self):
        """结果应按 order_score 降序排列。"""
        with patch.object(self.critic, "_fallback_evaluation") as mock_eval:
            scores = [60.0, 90.0, 75.0]
            idx = [0]
            def side_effect(subject: str, relation: str, obj: str) -> OrderedTriple:
                score = scores[idx[0] % len(scores)]
                idx[0] += 1
                return OrderedTriple(subject, relation, obj, order_score=score, confidence=0.8)
            mock_eval.side_effect = side_effect

            triples = [
                {"subject": "A", "relation": "r", "object": "X"},
                {"subject": "B", "relation": "r", "object": "Y"},
                {"subject": "C", "relation": "r", "object": "Z"},
            ]
            result = self.critic.filter_triples(triples, mode="balanced")
            scores_out = [t.order_score for t in result]
            assert scores_out == sorted(scores_out, reverse=True)

    def test_invalid_triple_skipped(self):
        """缺少主体或客体的三元组应被跳过。"""
        triples = [
            {"subject": "", "relation": "r", "object": "X"},
            {"subject": "A", "relation": "r", "object": ""},
            {"subject": "Federal Reserve", "relation": "raises", "object": "interest rates"},
        ]
        result = self.critic.filter_triples(triples, mode="balanced")
        # 只有完整三元组应被评估
        assert all(t.subject and t.object for t in result)

    def test_alias_field_names_supported(self):
        """支持 'from'/'to'/'predicate' 作为字段名的别名。"""
        triples = [
            {"from": "USA", "predicate": "sanctions", "to": "Iran"},
        ]
        result = self.critic.filter_triples(triples, mode="balanced")
        # 确保字段被正确解析（sanctions 含制裁含义，评分应 >= 50 或被兜底规则处理）
        for t in result:
            assert t.subject == "USA"
            assert t.object == "Iran"


# ---------------------------------------------------------------------------
# 缓存机制测试
# ---------------------------------------------------------------------------

class TestCacheMechanism:
    def test_same_triple_hits_cache(self):
        """相同三元组第二次调用应命中缓存，不重复调用 _fallback_evaluation。"""
        critic = OrderCritic(api_key=None)
        call_count = [0]
        original_fallback = critic._fallback_evaluation

        def counting_fallback(subject, relation, obj):
            call_count[0] += 1
            return original_fallback(subject, relation, obj)

        critic._fallback_evaluation = counting_fallback  # type: ignore[method-assign]

        critic.evaluate_triple("A", "B", "C")
        critic.evaluate_triple("A", "B", "C")  # 应命中缓存

        assert call_count[0] == 1  # 只被调用一次

    def test_clear_cache_resets(self):
        """clear_cache() 应清空缓存，使后续调用重新评估。"""
        critic = OrderCritic(api_key=None)
        call_count = [0]
        original_fallback = critic._fallback_evaluation

        def counting_fallback(subject, relation, obj):
            call_count[0] += 1
            return original_fallback(subject, relation, obj)

        critic._fallback_evaluation = counting_fallback  # type: ignore[method-assign]

        critic.evaluate_triple("X", "Y", "Z")
        critic.clear_cache()
        critic.evaluate_triple("X", "Y", "Z")  # 缓存已清空，应重新评估

        assert call_count[0] == 2

    def test_case_insensitive_cache_key(self):
        """缓存键应忽略大小写差异。"""
        critic = OrderCritic(api_key=None)
        r1 = critic.evaluate_triple("OpenAI", "Releases", "GPT-5")
        r2 = critic.evaluate_triple("openai", "releases", "gpt-5")
        # 两次应返回同一对象（缓存命中）
        assert r1 is r2


# ---------------------------------------------------------------------------
# LLM 路径测试（使用 mock）
# ---------------------------------------------------------------------------

class TestLLMPath:
    def test_llm_response_parsed_correctly(self):
        """LLM 返回正确 JSON 时应正确解析所有字段。"""
        critic = OrderCritic(api_key="fake-key-for-test")

        mock_response = MagicMock()
        mock_response.content = (
            '{"order_score": 88, "reasoning": "重大技术突破，具有长期影响", '
            '"category": "technology", "confidence": 0.92}'
        )
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        with patch("knowledge_layer.order_critic._build_llm") as mock_build:
            mock_llm = MagicMock()
            mock_build.return_value = mock_llm
            # Reset cached llm instance
            critic._llm = None
            with patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_prompt_cls:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_prompt_cls.return_value = mock_prompt

                result = critic.evaluate_triple("IBM", "achieves", "quantum supremacy")

        assert result.order_score == 88.0
        assert result.category == "technology"
        assert result.confidence == 0.92

    def test_llm_malformed_json_falls_back(self):
        """LLM 返回无效 JSON 时应安全降级，不抛出异常。"""
        critic = OrderCritic(api_key="fake-key-for-test")
        critic._api_key = "fake"  # 确保不走兜底的 api_key=None 分支

        with patch.object(critic, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            with patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_prompt_cls:
                mock_chain = MagicMock()
                mock_response = MagicMock()
                mock_response.content = "这不是有效的JSON格式！"
                mock_chain.invoke.return_value = mock_response
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_prompt_cls.return_value = mock_prompt

                # 由于 JSON 解析失败，会触发兜底逻辑
                result = critic.evaluate_triple("Singer", "posts", "selfie online")

        assert isinstance(result, OrderedTriple)
        assert 0.0 <= result.order_score <= 100.0


# ---------------------------------------------------------------------------
# 集成风格测试：完整过滤流程
# ---------------------------------------------------------------------------

class TestIntegrationScenarios:
    """验证完整过滤场景的行为一致性。"""

    def test_structural_info_preserved_trivial_filtered(self):
        """结构性信息保留，琐碎信息过滤的端到端验证。"""
        critic = OrderCritic(api_key=None)

        structural_triples = [
            {"subject": "Federal Reserve", "relation": "raises", "object": "interest rates"},
            {"subject": "NATO", "relation": "expands", "object": "military alliance"},
            {"subject": "OpenAI", "relation": "achieves", "object": "AGI breakthrough"},
        ]
        trivial_triples = [
            {"subject": "celebrity A", "relation": "gossip", "object": "celebrity party gossip"},
            {"subject": "singer B", "relation": "attends", "object": "entertainment award show"},
        ]

        all_triples = structural_triples + trivial_triples
        result = critic.filter_triples(all_triples, mode="balanced")

        # 至少有一些结构性信息被保留
        assert len(result) > 0
        # 所有保留的三元组分数 >= 50
        assert all(t.order_score >= 50.0 for t in result)

    def test_score_consistency(self):
        """对相同三元组多次调用，评分应一致（缓存保证）。"""
        critic = OrderCritic(api_key=None)
        triple = {"subject": "China", "relation": "launches", "object": "space station"}

        r1 = critic.filter_triples([triple], mode="balanced")
        r2 = critic.filter_triples([triple], mode="balanced")

        if r1 and r2:
            assert r1[0].order_score == r2[0].order_score
