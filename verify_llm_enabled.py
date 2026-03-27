#!/usr/bin/env python3
"""验证 LLM 是否启用"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 重新加载 .env
from dotenv import load_dotenv
load_dotenv()

from app.core.config import get_settings

settings = get_settings()

print("=" * 100)
print("【LLM 配置验证】")
print("=" * 100)

print(f"\n【环境变量】")
print(f"  • LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")
print(f"  • OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', 'not set')[:20] if os.getenv('OPENAI_API_KEY') else 'not set'}...")
print(f"  • GROQ_API_KEY: {os.getenv('GROQ_API_KEY', 'not set')[:20] if os.getenv('GROQ_API_KEY') else 'not set'}...")

print(f"\n【配置状态】")
print(f"  • llm_enabled: {settings.llm_enabled}")
print(f"  • llm_provider: {settings.llm_provider}")
print(f"  • llm_model: {settings.llm_model}")

if settings.llm_enabled:
    print(f"\n✅ LLM 已启用！")
else:
    print(f"\n❌ LLM 未启用！需要配置 OPENAI_API_KEY 或 GROQ_API_KEY")

print("\n" + "=" * 100)
