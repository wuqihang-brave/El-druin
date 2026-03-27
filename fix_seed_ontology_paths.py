#!/usr/bin/env python3
"""修复 seed_ontology.py 中的数据库路径"""

seed_file = "backend/knowledge_layer/seed_ontology.py"

with open(seed_file, 'r') as f:
    lines = f.readlines()

# 修改第 662 行和第 818 行
modified = False
for i in range(len(lines)):
    if './data/kuzu_db"' in lines[i] and './data/kuzu_db.db' not in lines[i]:
        lines[i] = lines[i].replace('./data/kuzu_db', './data/kuzu_db.db')
        print(f"✅ 第 {i+1} 行已修复")
        modified = True

if modified:
    with open(seed_file, 'w') as f:
        f.writelines(lines)
    print("\n✅ seed_ontology.py 已修复!")
else:
    print("✅ 无需修复")

