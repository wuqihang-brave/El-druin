from app.knowledge.graph_store import GraphStore
store = GraphStore()
print("== 实际DB路径:", getattr(store, "_db_path", "未知/属性名你得按实际取"))
# 或者 print(config里的路径。保证实际连接的文件就是唯一要用的那份！

store.add_entity("A", "Entity")
store.add_entity("B", "Entity")
store.add_relation(
    from_name = "A",
    from_type = "Entity",
    to_name   = "B",
    to_type   = "Entity",
    relation_type = "test_rel",
    weight    = 0.8
)
print("写入后实体数:", len(store.get_entities(limit=100)))
print("写入后边数:", len(store.get_relations(limit=100)))