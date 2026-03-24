"""
秩序评论家数据模型（Order Critic Data Models）

定义知识三元组的结构化输出格式，包含秩序评分、分类和置信度。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# 知识分类类型
CategoryType = Literal["technology", "geopolitics", "institution", "causality", "unknown"]


@dataclass
class OrderedTriple:
    """经过秩序评论家评估后的结构化知识三元组。

    Attributes:
        subject: 三元组的主体实体（Subject entity）。
        relation: 主体与客体之间的关系（Relation type）。
        object: 三元组的客体实体（Object entity）。
        order_score: 秩序评分，范围 0-100。分值越高表示信息越具结构性价值。
        reasoning: 评论家给出的评分理由说明。
        category: 知识分类，枚举值之一：
            - "technology"   – 技术突破、科学发现
            - "geopolitics"  – 地缘政治、国际关系变迁
            - "institution"  – 制度创新、法律框架、商业模式
            - "causality"    – 因果链条、系统性影响
            - "unknown"      – 无法归类
        confidence: 评论家对自身评估结果的置信度，范围 0.0-1.0。
    """

    subject: str
    relation: str
    object: str
    order_score: float = field(default=0.0)
    reasoning: str = field(default="")
    category: CategoryType = field(default="unknown")
    confidence: float = field(default=0.0)

    def __post_init__(self) -> None:
        # 约束评分到合法范围
        self.order_score = max(0.0, min(100.0, float(self.order_score)))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    @property
    def is_ordered(self) -> bool:
        """当秩序评分 >= 50 时，认为该三元组具有保留价值。"""
        return self.order_score >= 50.0

    def to_dict(self) -> dict:
        """返回 JSON 可序列化的字典形式。"""
        return {
            "subject": self.subject,
            "relation": self.relation,
            "object": self.object,
            "order_score": self.order_score,
            "reasoning": self.reasoning,
            "category": self.category,
            "confidence": self.confidence,
        }
