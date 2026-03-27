#!/usr/bin/env python3
"""手动构建 KuzuDB 连接"""

import kuzu
import os

print("=" * 100)
print("【KuzuDB 连接测试】")
print("=" * 100)

# 尝试不同的路径格式
paths = [
    "./data/kuzu_db",           # 目录
    "./data/kuzu_db.db",        # 文件
    "./data/el_druin.kuzu",     # 从 kuzu_graph.py 文件名
    "/tmp/test_kuzu",           # 临时目录
]

for db_path in paths:
    print(f"\n尝试路径: {db_path}")
    try:
        # 如果是目录，先创建
        if not db_path.endswith(".db") and not db_path.endswith(".kuzu"):
            os.makedirs(db_path, exist_ok=True)
            print(f"  已创建目录")
        
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        print(f"  ✅ 成功")
        
        # 测试查询
        result = conn.execute("MATCH (n) RETURN COUNT(*) as count")
        if result.has_next():
            count = result.get_next()[0]
            print(f"  实体数: {count}")
        
        break
    except Exception as e:
        print(f"  ❌ 失败: {type(e).__name__}: {str(e)[:80]}")

print("\n" + "=" * 100)
