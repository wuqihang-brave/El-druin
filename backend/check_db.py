import kuzu

db = kuzu.Database('data/el_druin_strict.kuzu')
conn = kuzu.Connection(db)

# 1. 检查节点数量
print("--- 节点统计 ---")
res = conn.execute("CALL SHOW_TABLES() RETURN name, type")
while res.has_next():
    row = res.get_next()
    if row[1] == 'NODE':
        count = conn.execute(f"MATCH (n:{row[0]}) RETURN count(*)").get_next()[0]
        if count > 0:
            print(f"表 {row[0]}: {count} 个实体")

# 2. 检查刚才录入的逻辑边
print("\n--- 逻辑边抽样 ---")
# 尝试查找刚才 text 里的 Yair Lapid
try:
    res = conn.execute("MATCH (a)-[r]->(b) RETURN a.name, type(r), b.name LIMIT 5")
    while res.has_next():
        print(res.get_next())
except:
    print("暂未查询到逻辑边关联。")