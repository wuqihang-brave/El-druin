#!/usr/bin/env python3
"""检查 LLM API 配置"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.config import get_settings

print("=" * 100)
print("【LLM API 配置检查】")
print("=" * 100)

settings = get_settings()

print(f"\n【配置信息】")
print(f"  • LLM 启用: {settings.llm_enabled}")
print(f"  • LLM 提供商: {settings.llm_provider}")
print(f"  • LLM 模型: {settings.llm_model}")
print(f"  • LLM 温度: {settings.llm_temperature}")

print(f"\n【API 密钥检查】")
if settings.llm_provider == "openai":
    api_key = settings.openai_api_key
    if api_key:
        print(f"  ✅ OpenAI API 密钥已配置: {api_key[:10]}...{api_key[-5:]}")
    else:
        print(f"  ❌ OpenAI API 密钥未配置！")
elif settings.llm_provider == "groq":
    api_key = settings.groq_api_key
    if api_key:
        print(f"  ✅ Groq API 密钥已配置: {api_key[:10]}...{api_key[-5:]}")
    else:
        print(f"  ❌ Groq API 密钥未配置！")

print(f"\n【测试 LLM 调用】")
try:
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key,
        )
    elif settings.llm_provider == "groq":
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.groq_api_key,
        )
    
    # 测试简单调用
    response = llm.invoke([("human", "Hello, world!")])
    print(f"  ✅ LLM 连接成功")
    print(f"  Response: {str(response.content)[:100]}")
    
except Exception as e:
    print(f"  ❌ LLM 调用失败: {e}")

print("\n" + "=" * 100)
