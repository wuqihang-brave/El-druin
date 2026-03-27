import kuzu
import json
import os

def init_kuzu_rel_tables(relations_json_path, db_path='./data/kuzu_db.db'): 
    # 1. 连接数据库
    if not os.path.exists(db_path):
        print(f"❌ 数据库路径 {db_path} 不存在，请确认路径。")
        return
    
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # 2. 获取所有已存在的节点表名
    result = conn.execute("CALL SHOW_TABLES() RETURN name, type")
    node_tables = []
    while result.has_next():
        row = result.get_next()
        if row[1] == 'NODE':
            node_tables.append(row[0])
    
    if not node_tables:
        print("❌ 未发现任何节点表，无法创建关系。")
        return

    # 3. 加载逻辑边定义
    if not os.path.exists(relations_json_path):
        print(f"❌ 找不到配置文件: {relations_json_path}")
        return

    with open(relations_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    relations = data.get("relations", [])
    print(f"🔗 数据库路径: {db_path}")
    print(f"🔗 检测到节点表共 {len(node_tables)} 个")
    print(f"🔗 开始构建逻辑边体系，共计 {len(relations)} 种关系类型...")

    # 4. 核心修复逻辑：生成显式的 FROM...TO 对列表
    # KuzuDB 不支持 FROM T1, T2 TO T3, T4，必须写成 FROM T1 TO T3, FROM T1 TO T4...
    rel_pairs = []
    for src_table in node_tables:
        for dst_table in node_tables:
            rel_pairs.append(f"FROM {src_table} TO {dst_table}")
    
    # 将所有配对用逗号连接
    rel_groups_str = ", ".join(rel_pairs)

    for rel in relations:
        rel_name = rel['label']
        
        # 构造符合 KuzuDB 规范的 DDL 语句
        # 结构：CREATE REL TABLE 名字 (所有的 FROM-TO 对, 属性列表, 基数)
        create_rel_query = (
            f"CREATE REL TABLE {rel_name} ("
            f"{rel_groups_str}, "
            f"confidence DOUBLE, "
            f"source_ref STRING, "
            f"description STRING, "
            f"MANY_MANY)"
        )
        
        try:
            conn.execute(create_rel_query)
            print(f"✅ 已成功创建多表连接关系: {rel_name}")
        except Exception as e:
            if "already exists" in str(e):
                print(f"⏩ 跳过已存在的边: {rel_name}")
            else:
                print(f"❌ 创建边 {rel_name} 失败: {e}")

    print("\n✨ KuzuDB 逻辑边初始化完成！")

if __name__ == "__main__":
    # 确保路径与你的项目结构一致
    REL_JSON = "backend/config/relations.json"
    init_kuzu_rel_tables(REL_JSON)