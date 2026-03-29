import kuzu

db_path = "./data/kuzu_db.db"
db = kuzu.Database(db_path)
conn = kuzu.Connection(db)

print("\n【节点总数】")
print(conn.execute("MATCH (n) RETURN COUNT(n)").get_next()[0])

print("\n【边总数】")
print(conn.execute("MATCH ()-[r]->() RETURN COUNT(r)").get_next()[0])

print("\n【前20个三元组】")
query = "MATCH (a)-[r]->(b) RETURN a.name, b.name LIMIT 20"
result = conn.execute(query)
while result.has_next():
    print(result.get_next())