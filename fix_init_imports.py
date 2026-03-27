#!/usr/bin/env python3
"""修复 __init__.py 导入"""

init_file = "backend/knowledge_layer/__init__.py"

# 读取原文件
with open(init_file, 'r') as f:
    content = f.read()

# 替换所有错误的导入
new_content = content.replace(
    "from knowledge_layer.",
    "from backend.knowledge_layer."
)

# 写回
with open(init_file, 'w') as f:
    f.write(new_content)

print("✅ 已修复!")
print("\n修改前:")
print(content)
print("\n修改后:")
print(new_content)
