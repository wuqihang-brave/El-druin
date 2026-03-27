import kuzu
import json
import os
import logging
from typing import Dict, Any

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class SeedOntology:
    def __init__(self, db_path: str = "./data/kuzu_db.db", ontology_path: str = "backend/config/ontology_subset.json"):
        self.db_path = db_path
        self.ontology_path = ontology_path
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 连接数据库
        self.db = kuzu.Database(self.db_path)
        self.conn = kuzu.Connection(self.db)
        
        # 加载本体定义
        self.ontology = self._load_json(self.ontology_path)

    def _load_json(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            logger.error(f"找不到配置文件: {path}")
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_existing_tables(self) -> list:
        """获取数据库中已存在的表名"""
        result = self.conn.execute("CALL SHOW_TABLES() RETURN name")
        tables = []
        while result.has_next():
            tables.append(result.get_next()[0])
        return tables

    def create_node_tables(self):
        """核心修复：根据 ontology_subset.json 动态创建所有独立的节点表"""
        classes = self.ontology.get("classes", {})
        existing_tables = self._get_existing_tables()
        
        logger.info(f"开始初始化节点表，目标类别数: {len(classes)}")
        
        for class_name in classes:
            if class_name in existing_tables:
                logger.info(f"⏩ 跳过已存在的表: {class_name}")
                continue
            
            try:
                # 每个类别创建一个独立的 NODE TABLE，统一主键为 name
                query = f"CREATE NODE TABLE {class_name}(name STRING, description STRING, PRIMARY KEY (name))"
                self.conn.execute(query)
                logger.info(f"✅ 成功创建节点表: {class_name}")
            except Exception as e:
                logger.error(f"❌ 创建表 {class_name} 失败: {e}")

    def seed_initial_data(self):
        """可选：在这里可以加入一些基础数据的 MERGE 逻辑"""
        # 示例：创建一个默认的管理员或系统节点
        if "Person" in self._get_existing_tables():
            self.conn.execute("MERGE (p:Person {name: 'System_Admin', description: 'Initial seed entity'})")

def main():
    # 1. 物理重置（如果需要彻底重新开始，建议手动执行 rm -rf data/kuzu_db.db）
    
    seeder = SeedOntology()
    
    print("\n" + "="*50)
    print("🚀 EL-DRUIN 节点表初始化程序 (方案 A)")
    print("="*50)
    
    # 2. 执行建表逻辑
    seeder.create_node_tables()
    
    # 3. 灌入基础数据
    seeder.seed_initial_data()
    
    print("\n" + "="*50)
    print("🎯 初始化完成！所有本体类别已映射为 KuzuDB 节点表。")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()