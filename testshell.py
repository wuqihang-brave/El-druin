import kuzu
db = kuzu.Database('./data/el_druin.kuzu') 
conn = kuzu.Connection(db)

print("实体节点数:", conn.execute("MATCH (n:Entity) RETURN count(n)").get_next()[0])  # 或 Person/ORG 等
print("全部边数:", conn.execute("MATCH (a)-[r]->(b) RETURN count(r)").get_next()[0])

# 对每种关系类型采样一下
for rel in ["RELATED_TO", "LOCATED_IN", "OPPOSES", "CAUSES"]:
    try:
        print(f"{rel} 边数:", conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r)").get_next()[0])
    except Exception:
        pass

# 抽样看部分真实边
result = conn.execute("MATCH (a)-[r]->(b) RETURN a.name, label(r), b.name LIMIT 10")
while result.has_next():
    print(result.get_next())