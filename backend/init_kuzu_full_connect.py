import kuzu
import json
import os

def init_kuzu_full_connect(relations_json_path, db_path='data/el_druin_strict.kuzu'):
    if not os.path.exists(db_path):
        print(f"❌ 数据库路径 {db_path} 不存在。")
        return
    
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # 1. 获取所有节点表名
    result = conn.execute("CALL SHOW_TABLES() RETURN name, type")
    node_tables = []
    while result.has_next():
        row = result.get_next()
        if row[1] == 'NODE':
            node_tables.append(str(row[0]).strip())
    
    # 2. 加载关系定义
    with open(relations_json_path, 'r', encoding='utf-8') as f:
        rel_data = json.load(f)
    relations = rel_data.get("relations", [])

    print(f"🚀 开始笛卡尔积建模：{len(node_tables)} 节点类 x {len(relations)} 关系动词")

    for rel in relations:
        rel_label = rel['label'].strip()
        
        # 核心逻辑：在 KuzuDB 中，一个 REL TABLE 可以定义多个连接对
        # 语法：CREATE REL TABLE label (FROM TableA TO TableB, FROM TableC TO TableD, ...)
        
        connection_pairs = []
        for src in node_tables:
            for dst in node_tables:
                connection_pairs.append(f"FROM {src} TO {dst}")
        
        # 将所有组合连接成字符串
        pairs_str = ", ".join(connection_pairs)
        
        create_rel_query = f"""
            CREATE REL TABLE {rel_label} (
                {pairs_str},
                confidence DOUBLE,
                source_ref STRING,
                description STRING,
                MANY_MANY
            )
        """
        
        try:
            conn.execute(create_rel_query)
            print(f"✅ 逻辑全连接成功: {rel_label} (已覆盖所有节点组合)")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"⏩ 跳过: {rel_label} (已存在)")
            else:
                print(f"❌ 失败: {rel_label} -> {str(e)[:100]}...")

if __name__ == "__main__":
    init_kuzu_full_connect("backend/config/relations.json")