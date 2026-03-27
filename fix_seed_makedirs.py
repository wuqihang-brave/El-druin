#!/usr/bin/env python3
"""修复 seed_ontology.py 中的 makedirs 问题"""

seed_file = "backend/knowledge_layer/seed_ontology.py"

with open(seed_file, 'r') as f:
    content = f.read()

# 找到问题的行并修复
# os.makedirs(db_path, exist_ok=True) 应该改为 os.makedirs(os.path.dirname(db_path), exist_ok=True)

new_content = content.replace(
    "os.makedirs(db_path, exist_ok=True)",
    "os.makedirs(os.path.dirname(db_path), exist_ok=True)"
)

if new_content != content:
    with open(seed_file, 'w') as f:
        f.write(new_content)
    print("✅ 已修复 makedirs 问题!")
else:
    print("✅ 无需修复")

