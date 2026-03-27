import os, json, kuzu, re
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

class ExtractorAgent:
    def __init__(self, db_path='./data/kuzu_db.db'):
        self.llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.0)
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self.ontology = json.load(open("backend/config/ontology_subset.json"))
        self.relations = json.load(open("backend/config/relations.json"))
        
        self.NODE_MAP = {k.upper(): k for k in self.ontology['classes'].keys()}
        self.EDGE_MAP = {r['label'].upper().replace("-", "_"): r['label'] for r in self.relations['relations']}
        self.WEIGHT_MAP = {r['label']: r.get('logic_weight', 0.5) for r in self.relations['relations']}

    def _generate_system_prompt(self):
        # 核心改进：明确要求 source/target 结构
        return f"""
        你是一个专业的情报提取专家。必须将文本转换为三元组 JSON 数组。
        每个对象必须严格包含: "source", "source_type", "target", "target_type", "edge", "confidence", "desc"。
        
        [允许节点类型]: {list(self.NODE_MAP.values())}
        [允许关系类型]: {list(self.EDGE_MAP.values())}
        
        示例输出:
        [
          {{"source": "墨西哥海军", "source_type": "Organization", "target": "古巴", "target_type": "Location", "edge": "mitigates", "confidence": 0.9, "desc": "运送物资"}}
        ]
        """

    def push_to_kuzu(self, triplets):
        print(f"\n--- KuzuDB 同步开始 (共 {len(triplets)} 条) ---")
        for tri in triplets:
            try:
                # 1. 字段提取与清洗 (处理 LLM 可能输出的 key 变体)
                s_name_raw = tri.get('source') or tri.get('name') or "Unknown"
                t_name_raw = tri.get('target') or "Global Context"
                
                s_type = self.NODE_MAP.get(str(tri.get('source_type')).upper(), "Event")
                t_type = self.NODE_MAP.get(str(tri.get('target_type')).upper(), "Event")
                
                edge_raw = str(tri.get('edge', 'indicates')).upper().replace("-", "_")
                edge = self.EDGE_MAP.get(edge_raw, "indicates")
                weight = self.WEIGHT_MAP.get(edge, 0.5)

                s_name = str(s_name_raw).replace("'", "''")
                t_name = str(t_name_raw).replace("'", "''")
                desc = str(tri.get('desc', '')).replace("'", "''")

                # 2. Upsert 节点
                for name, label in [(s_name, s_type), (t_name, t_type)]:
                    if not self.conn.execute(f"MATCH (n:{label}) WHERE n.name='{name}' RETURN n").has_next():
                        self.conn.execute(f"CREATE (n:{label} {{name: '{name}', description: 'Auto-extracted'}})")

                # 3. 创建关系
                sql = (f"MATCH (s:{s_type}), (t:{t_type}) WHERE s.name='{s_name}' AND t.name='{t_name}' "
                       f"CREATE (s)-[r:{edge} {{logic_weight: {weight}, confidence: {tri.get('confidence', 0.5)}, description: '{desc}'}}]->(t)")
                self.conn.execute(sql)
                print(f"✅ [成功] {s_name} --[{edge}]--> {t_name} (Weight: {weight})")
                
            except Exception as e:
                print(f"❌ [异常]: {e}")

    def extract_and_sync(self, text):
        res = self.llm.invoke([("system", self._generate_system_prompt()), ("human", text)])
        match = re.search(r'\[.*\]', res.content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            print("\n--- LLM 结构化提取结果 ---")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            self.push_to_kuzu(data)

if __name__ == "__main__":
    agent = ExtractorAgent()
    # 运行你要求的地缘政治推演测试文本
    test_text = "The cyber-attack on the power plant, attributed to a foreign actor, causes severe energy shortages, which compromises the regional stability."
    agent.extract_and_sync(test_text)