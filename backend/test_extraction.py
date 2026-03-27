from backend.agents.extractor_agent import ExtractorAgent

agent = ExtractorAgent()

# 测试一段带有典型 STIX 逻辑的文本
test_text = """
Recent intelligence indicates that the hacker group 'DarkQuad' is using 
custom malware to target the energy infrastructure in Mexico, 
potentially causing massive power outages.
"""

print("正在执行提取测试...")
agent.extract_and_sync(test_text)