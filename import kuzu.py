import kuzu

db = kuzu.Database("./data/el_druin.kuzu")
conn = kuzu.Connection(db)
# 创建schema（只第一次需要）
conn.execute("CREATE NODE TABLE IF NOT EXISTS Entity(name STRING, description STRING, PRIMARY KEY (name))")
# 插入节点
conn.execute("CREATE (:Entity {name: '中国', description: '中华人民共和国'})")
conn.execute("CREATE (:Entity {name: '美国', description: '美利坚合众国'})")
# 查询插入数据
result = conn.execute("MATCH (n:Entity) RETURN n.name, n.description")
print([row for row in result])