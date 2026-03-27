import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# 1. 加载 .env 文件
load_dotenv()

# 2. 获取环境变量
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    # 给出明确提示，防止程序静默崩溃
    raise ValueError("❌ 未找到 GROQ_API_KEY。请检查 .env 文件或系统环境变量。")

try:
    # 3. 初始化模型
    # 注意：LangChain 的 Groq 集成通常使用 groq_api_key 作为参数名
    llm = ChatGroq(
        groq_api_key=api_key, 
        model_name="llama-3.1-8b-instant",  # 确保这里写对
        temperature=0.1  # 对于本体分析，建议低随机性
    )
    
    print("✅ Llama 3.1 8B Instant 连接成功！")
except Exception as e:
    print(f"❌ 初始化失败: {e}")