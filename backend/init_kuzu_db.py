import kuzu
import json
import os

def init_el_druin_db(
    ontology_json_path="backend/config/ontology_subset.json",
    db_path="data/el_druin_strict.kuzu"
):
    # 1. 数据库文件夹及文件确认
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    print(f"🚀 打开/创建 Kuzu 数据库：{db_path}")
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # 2. 加载本体
    with open(ontology_json_path, "r", encoding="utf-8") as f:
        ontology = json.load(f)
    classes = ontology.get("classes", {})

    print(f"📚 本体核心类数：{len(classes)}")

    # 3. 创建节点表
    for label in classes.keys():
        table_name = label.upper().replace(" ", "_").replace("-", "_")
        try:
            query = f"""
            CREATE NODE TABLE {table_name} (
                name STRING,
                description STRING,
                uri STRING,
                last_updated STRING,
                PRIMARY KEY (name)
            )
            """
            conn.execute(query)
            print(f"✅ 节点表已创建: {table_name}")
        except Exception as e:
            if "already exists" in str(e):
                print(f"⏩ 已存在，跳过: {table_name}")
            else:
                print(f"❌ 创建 {table_name} 出错: {e}")

    # 4. 创建常用关系
    # 你可在此自定义更多“边”类型
    common_edges = [
        ("MENTIONS", "PERSON", "SOFTWAREAPPLICATION"),
        ("RELATED_TO", "ORGANIZATION", "PROJECT"),
        ("LOCATED_IN", "ORGANIZATION", "PLACE"),
        ("INVOLVED_IN", "PERSON", "EVENT"),
        ("AFFECTS", "MALWARE", "SOFTWAREAPPLICATION"),
        ("HAS_ROLE", "PERSON", "ROLE")
    ]
    print("🔗 开始创建关系表 ...")
    for edge_name, src, dst in common_edges:
        try:
            query = f"CREATE REL TABLE {edge_name} (FROM {src} TO {dst})"
            conn.execute(query)
            print(f"✅ 关系表已创建: {edge_name} ({src}→{dst})")
        except Exception as e:
            if "already exists" in str(e):
                print(f"⏩ 已存在，跳过: {edge_name}")
            else:
                print(f"❌ 创建关系 {edge_name} 出错: {e}")

    print("✨ 数据库本体建模完成！")

if __name__ == "__main__":
    init_el_druin_db()