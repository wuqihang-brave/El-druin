import os
import json
import kuzu
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

class ExtractorAgent:
    def __init__(self, db_path='./data/kuzu_db.db'):
        self.llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.1-8b-instant",
            temperature=0.0 
        )
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self.ontology = self._load_config("backend/config/ontology_subset.json")
        self.relations = self._load_config("backend/config/relations.json")
        
        # 归一化映射表
        self.NODE_MAP = {k.upper(): k for k in self.ontology['classes'].keys()}
        self.EDGE_MAP = {r['label'].upper(): r['label'] for r in self.relations['relations']}

    def _load_config(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _generate_system_prompt(self):
        node_list = ", ".join(self.NODE_MAP.values())
        edge_list = ", ".join(self.EDGE_MAP.values())
        return f"""
        你是一个专业的情报提取专家。提取三元组并输出纯 JSON 数组。
        
        [字段要求 - 必须包含]:
        1. source: 实体A名称
        2. source_type: 实体A类型 (必须属于: [{node_list}])
        3. target: 实体B名称
        4. target_type: 实体B类型 (必须属于: [{node_list}])
        5. edge: 关系标签 (必须属于: [{edge_list}])
        6. confidence: 0-1 浮点数
        7. desc: 简短说明
        """

    def push_to_kuzu(self, triplets):
        print(f"\n--- KuzuDB 同步开始 (共 {len(triplets)} 条) ---")
        for tri in triplets:
            try:
                # --- 别名兼容逻辑 (处理 LLM 可能输出 subject/predicate 的情况) ---
                s_name_raw = tri.get('source') or tri.get('subject')
                t_name_raw = tri.get('target') or tri.get('object')
                edge_raw = tri.get('edge') or tri.get('predicate')
                
                # 尝试根据上下文猜测类型 (如果 LLM 漏掉了 type 字段)
                s_type_raw = tri.get('source_type', 'Person').strip().upper() 
                t_type_raw = tri.get('target_type', 'Organization').strip().upper()
                raw_edge = edge_raw.strip().upper() if edge_raw else ""

                # 标签校准
                s_type = self.NODE_MAP.get(s_type_raw)
                t_type = self.NODE_MAP.get(t_type_raw)
                edge = self.EDGE_MAP.get(raw_edge) or "mentions"

                if not s_type or not t_type or not s_name_raw or not t_name_raw:
                    print(f"❌ [丢弃] 关键字段缺失或类型非法 | 数据: {tri}")
                    continue

                s_name = str(s_name_raw).replace("'", "''")
                t_name = str(t_name_raw).replace("'", "''")

                # Upsert 节点
                for name, label in [(s_name, s_type), (t_name, t_type)]:
                    if not self.conn.execute(f"MATCH (n:{label}) WHERE n.name='{name}' RETURN n").has_next():
                        self.conn.execute(f"CREATE (n:{label} {{name: '{name}', description: 'Auto-extracted'}})")

                # 创建边
                sql = (f"MATCH (s:{s_type}), (t:{t_type}) WHERE s.name='{s_name}' AND t.name='{t_name}' "
                       f"CREATE (s)-[r:{edge} {{confidence: {tri.get('confidence', 0.5)}, description: '{tri.get('desc', '')}'}}]->(t)")
                self.conn.execute(sql)
                print(f"✅ [成功] {s_name} --[{edge}]--> {t_name}")
                
            except Exception as e:
                print(f"❌ [异常] {e}")

    def extract_and_sync(self, text):
        response = self.llm.invoke([("system", self._generate_system_prompt()), ("human", text)])
        try:
            content = response.content.replace("```json", "").replace("```", "").strip()
            results = json.loads(content)
            print("\n--- LLM 三元组原始输出 ---")
            print(json.dumps(results, indent=2, ensure_ascii=False))
            self.push_to_kuzu(results)
            return results
        except Exception as e:
            print(f"❌ 流程失败: {e}")
            return None

if __name__ == "__main__":
    agent = ExtractorAgent()
    agent.extract_and_sync("Yair Lapid is a leader of the opposition.")