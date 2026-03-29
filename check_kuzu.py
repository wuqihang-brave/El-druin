#!/usr/bin/env python3
"""快速检查 KuzuDB 状态"""

import os
import sys

print("=" * 80)
print("🔍 KuzuDB 状态检查")
print("=" * 80)

# 检查目录
db_path = "./data/kuzu_db.db"
data_dir = os.path.dirname(db_path)
if not os.path.exists(data_dir):
    os.makedirs(data_dir, exist_ok=True)
print(f"检查数据库文件: {db_path}")
...
if not os.path.exists(db_path):
    print("❌ 数据库不存在")
else:
    print("✅ 数据库文件存在")
print(f"\n1️⃣ 检查数据目录: {data_dir}")
if os.path.exists(data_dir):
    print("✅ 目录存在")
    files = os.listdir(data_dir)
    if files:
        print(f" 内容: {files}")
    else:
        print(" ⚠️ 目录为空(正常, 等待初始化)")
else:
    print(f"❌ 目录不存在，创建中...")
    os.makedirs(data_dir, exist_ok=True)
    print("✅ 目录已创建")

# 尝试连接 KuzuDB
print(f"\n2️⃣ 尝���连接 KuzuDB")
try:
    import kuzu
    print(f"✅ kuzu 库已加载")
    
    db = kuzu.Database(db_path)
    print(f"✅ 数据库实例创建")
    
    conn = kuzu.Connection(db)
    print(f"✅ 连接已建立")
    
    # 运行查询
    result = conn.execute("MATCH (n) RETURN COUNT(*) as count")
    count = 0
    if result.has_next():
        row = result.get_next()
        count = row[0]
    
    print(f"\n3️⃣ 查询结果")
    print(f"✅ 数据库中的实体数: {count}")
    
    if count == 0:
        print(f"\n⚠️ 数据库为空")
        print(f"   需要运行: python -m backend.knowledge_layer.seed_ontology")
    else:
        print(f"\n✅ 数据库已初始化，���含 {count} 个实体")
    
except ImportError as e:
    print(f"❌ kuzu 未安装: {e}")
    print(f"   运行: pip install kuzu")
except Exception as e:
    print(f"❌ 连接失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
