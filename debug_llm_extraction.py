#!/usr/bin/env python3
"""调试 LLM 提取过程"""

import os
import sys
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 启用详细日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from app.knowledge.entity_extractor import OntologyConstrainedExtractor

test_news = "Google is launching Search Live globally. This AI-powered search enables real-time assistance via phone camera."

print("=" * 100)
print("【调试 LLM 提取】")
print("=" * 100)

extractor = OntologyConstrainedExtractor()

# 检查设置
print(f"\n【设置检查】")
settings = extractor._settings
print(f"  • LLM 启用: {settings.llm_enabled}")
print(f"  • LLM 提供商: {settings.llm_provider}")
print(f"  • LLM 模型: {settings.llm_model}")

# 获取系统提示词
print(f"\n【系统提示词】")
system_prompt = extractor._get_system_prompt()
print(f"  • 长度: {len(system_prompt)} 字符")
print(f"  • 前 200 字符:\n{system_prompt[:200]}")

# 提取实体
print(f"\n【实体提取】")
result = extractor.extract(test_news)

entities = result.get("entities", [])
relations = result.get("relations", [])
report = result.get("validation_report", {})

print(f"\n✅ 提取结果:")
print(f"  • 实体数: {len(entities)}")
print(f"  • 关系数: {len(relations)}")
print(f"  • 合规率: {report.get('compliance_pct')}%")

print(f"\n【提取的实体详情】")
for e in entities:
    print(f"  {json.dumps(e, ensure_ascii=False)}")

print(f"\n【提取的关系详情】")
for r in relations:
    print(f"  {json.dumps(r, ensure_ascii=False)}")

print(f"\n【验证报告】")
print(f"  • 有效实体: {len(report.get('valid_entities', []))}")
print(f"  • 无效实体: {len(report.get('invalid_entities', []))}")
print(f"  • 有效关系: {len(report.get('valid_edges', []))}")
print(f"  • 无效关系: {len(report.get('invalid_edges', []))}")

if report.get('invalid_entities'):
    print(f"\n【无效实体】")
    for invalid in report['invalid_entities']:
        print(f"  {json.dumps(invalid, ensure_ascii=False)}")

if report.get('invalid_edges'):
    print(f"\n【无效关系】")
    for invalid in report['invalid_edges']:
        print(f"  {json.dumps(invalid, ensure_ascii=False)}")

print("\n" + "=" * 100)
