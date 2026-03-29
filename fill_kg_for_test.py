import sys
sys.path.append("/Users/qihang/Desktop/test/El-druin/backend/agents")   # 绝对路径

from extractor_agent import ExtractorAgent

agent = ExtractorAgent(db_path="./data/kuzu_db.db")

agent.extract_and_sync("The US imposed sanctions on Iran on Monday.")
agent.extract_and_sync("Israel launched a cyber attack on Iran's nuclear facility.")
agent.extract_and_sync("Russia and China signed a new bilateral trade deal.")
agent.extract_and_sync("Germany joined the European Union.")
agent.extract_and_sync("President Donald met with Homeland Security officials.")
print("知识图谱测试数据插入完成！")