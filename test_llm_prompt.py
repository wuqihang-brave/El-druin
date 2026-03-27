#!/usr/bin/env python3
"""检查 LLM 提示词内容"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.config.ontology import generate_ontology_system_prompt, CORE_ONTOLOGY

# 获取提示词
prompt = generate_ontology_system_prompt()

print("=" * 100)
print("【LLM 系统提示词分析】")
print("=" * 100)

# 检查提示词中是否包含关系类型
print(f"\n提示词长度: {len(prompt)} 字符")

print(f"\n✅ 检查关系定义:")
relationships_in_prompt = ["mentions", "involved_in", "caused_by", "impacts", "works_for"]
for rel in relationships_in_prompt:
    if rel in prompt:
        print(f"   ✅ {rel} 包含在提示词中")
    else:
        print(f"   ❌ {rel} 不在提示词中")

print(f"\n✅ 检查实体类型定义:")
entity_types = ["Organization", "Person", "SoftwareApplication", "Event"]
for etype in entity_types:
    if etype in prompt:
        print(f"   ✅ {etype} 包含在提示词中")
    else:
        print(f"   ❌ {etype} 不在提示词中")

print(f"\n【提示词前 1000 字符】:")
print(prompt[:1000])

print(f"\n【提示词后 1000 字符】:")
print(prompt[-1000:])

print("\n" + "=" * 100)
