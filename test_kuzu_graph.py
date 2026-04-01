import kuzu

db_path = './data/kuzu_db.db'   # 修改为你的实际 kuzu db 路径
db = kuzu.Database(db_path)
conn = kuzu.Connection(db)

query = "MATCH (a)-[r]->(b) RETURN count(*)"
result = conn.execute(query)
print("KG 边总数 count: ", result.get_next()[0])

# 再随便采样10条边看看关系真实存在
query2 = "MATCH (a)-[r]->(b) RETURN a.name, type(r), b.name LIMIT 10"
result2 = conn.execute(query2)
while result2.has_next():
    print(result2.get_next())