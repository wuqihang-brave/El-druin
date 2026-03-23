# El-druin 🛡️
EL'druin - AI-Powered Ontology-Driven Intelligence Platform Open-source, federated event monitoring and future prediction system with  multi-agent analysis, real-time data fusion, and enterprise-grade security. Combines real-time event tracking with advanced predictive analytics. 



## 快速开始 / Quick Start

### 前置要求 / Prerequisites
- Git
- Python 3.8+（本地部署）或 Docker & Docker Compose（推荐）

### 1. 克隆项目
\`\`\`bash
git clone https://github.com/wuqihang-brave/El-druin.git
cd El-druin
\`\`\`

### 2. 配置环境变量
\`\`\`bash
cp .env.example .env
\`\`\`

**编辑 `.env` 文件，填入你的 API Key**（例如：OpenAI API Key、新闻源 API 等）

---

### 3. 选择运行方式

#### 选项 A: Docker 快速启动 🐳 （推荐）
\`\`\`bash
docker-compose up -d
\`\`\`

然后访问：
- **Streamlit UI**: http://localhost:8501
- **后端 API**: http://localhost:8000

停止服务：
\`\`\`bash
docker-compose down
\`\`\`

---

#### 选项 B: 本地环境手动安装

**3.1 创建虚拟环境**
\`\`\`bash
python -m venv venv
\`\`\`

**3.2 激活虚拟环境**

Linux/macOS:
\`\`\`bash
source venv/bin/activate
\`\`\`

Windows:
\`\`\`bash
.\\venv\\Scripts\\activate
\`\`\`

**3.3 安装依赖**
\`\`\`bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r frontend/requirements.txt
\`\`\`

**3.4 启动应用**

启动 Streamlit 前端：
\`\`\`bash
streamlit run frontend/app.py
\`\`\`

然后访问：http://localhost:8501

---

## 配置说明 / Configuration

### 环境变量说明

编辑 `.env` 文件，配置以下内容：

\`\`\`
# LLM 配置
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here

# 数据库配置
DB_TYPE=kuzu  # 或其他数据库类型
DB_PATH=./data/knowledge_graph.db

# 新闻源配置
NEWS_API_KEY=your_news_api_key_here
\`\`\`

更详细的配置选项见 [.env.example](.env.example)

---

## 项目结构 / Project Structure

\`\`\`
El-druin/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── data_ingestion/  # 数据摄入模块
│   │   ├── knowledge/       # 知识图谱模块
│   │   └── main.py
│   └── requirements.txt
├── frontend/                # Streamlit 前端
│   ├── app.py
│   ├─�� pages/              # 各个功能页面
│   ├── utils/              # 工具函数
│   └── requirements.txt
├── config.py               # 全局配置
├── docker-compose.yml      # Docker 编排
└── README.md
\`\`\`

---

## 故障排除 / Troubleshooting

### 问题：导入错误
如果遇到 \`ImportError\`，确保：
1. 虚拟环境已激活
2. 所有依赖已安装：\`pip install -r requirements.txt\`
3. 在项目根目录运行命令

### 问题：API Key 无效
检查 \`.env\` 文件中的 API Key 是否正确填入

### ��题：端口被占用
\`\`\`bash
# 查看占用 8501 端口的进程
lsof -i :8501

# Streamlit 使用其他端口
streamlit run frontend/app.py --server.port 8502
\`\`\`

---

## 下一步 / Next Steps

- 📖 查看 [项目文档](./docs)
- 🚀 运行示例
- 📊 了解知识图谱功能

