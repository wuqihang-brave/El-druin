# El-druin 🛡️

EL'druin - AI-Powered Ontology-Driven Intelligence Platform. Open-source, federated event monitoring and future prediction system with multi-agent analysis, real-time data fusion, and enterprise-grade security. Combines real-time event tracking with advanced predictive analytics.

---

## 🚀 快速开始 / Quick Start

### 前置要求 / Prerequisites
- **Git**
- **Python 3.9+** (本地部署)
- **Docker & Docker Compose** (推荐方式)

### 1. 克隆项目
```bash
git clone https://github.com/wuqihang-brave/El-druin.git
cd El-druin
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key (如 OpenAI, News API 等)
nano .env
```

---

### 3. 选择运行方式

#### 选项 A: Docker 快速启动 🐳 (推荐)
```bash
docker-compose up -d
```

成功启动后访问：
- **Streamlit UI**: http://localhost:8501
- **后端 API**: http://localhost:8001

停止服务：
```bash
docker-compose down
```

---

#### 选项 B: 本地开发环境安装

```bash
# 3.1 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# 3.2 安装依赖
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt

# 3.3 创建数据存储目录
mkdir -p data

# 3.4 启动 Streamlit 前端
streamlit run frontend/app.py
```

然后访问：http://localhost:8501

---

## ⚙️ 配置说明 / Configuration

### 环境变量详解

编辑 `.env` 文件，确保以下核心项已配置：

| 变量名 | 说明 | 示例 |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | 模型提供商 | `openai` / `groq` / `none` |
| `OPENAI_API_KEY` | OpenAI 密钥 | `sk-xxxx...` |
| `GROQ_API_KEY` | Groq 密钥 | `gsk_xxxx...` |
| `GRAPH_BACKEND` | 图数据库类型 | `kuzu` / `networkx` |
| `KUZU_DB_PATH` | Kuzu 数据库路径 | `./data/kuzu_db` |
| `NEWSAPI_KEY` | NewsAPI 密钥 | `your_key_here` |
| `API_PORT` | 后端 API 端口 | `8001` |

更详细的配置选项见 [.env.example](.env.example)

---

## 📂 项目结构 / Project Structure

```text
El-druin/
├── backend/                # 后端核心：摄入、知识层、API
│   ├── app/
│   │   ├── api/            # FastAPI 路由
│   │   ├── core/           # 核心配置
│   │   ├── data_ingestion/ # 数据抓取与预处理
│   │   └── knowledge/      # Kuzu 图数据库逻辑
│   ├── main.py             # 后端入口
│   └── requirements.txt
├── frontend/               # UI 界面：Streamlit 驱动
│   ├── app.py              # 主入口
│   ├── pages/              # 功能模块页面
│   ├── utils/              # 工具函数
│   └── requirements.txt
├── data/                   # 本地持久化数据
├── config.py               # 全局配置读取
├── docker-compose.yml      # 容器化编排
└── .env.example            # 环境变量模板
```

---

## 🛠️ 故障排除 / Troubleshooting

- **ImportError**: 检查是否激活了 venv，并确保分别运行了 `pip install -r backend/requirements.txt` 和 `pip install -r frontend/requirements.txt`。
- **Kuzu Database Error**: 确保 `data/` 目录存在且有写入权限：`mkdir -p data`。
- **API Key 无效**: 检查 `.env` 文件中的 API Key 是否正确填入，注意不要有多余的空格。
- **端口占用**: Streamlit 默认 8501，后端 API 默认 8001。若冲突，请使用 `streamlit run frontend/app.py --server.port 8502`。
- **Docker 容器无法启动**: 运行 `docker-compose logs` 查看详细错误信息。

---

## 🌐 初始化知识图谱本体 / Seed Ontology Data

首次启动后，**推荐运行一次**以下命令初始化 KuzuDB 本体数据，获得更丰富的推演上下文：

```bash
python -m backend.knowledge_layer.seed_ontology
```

该脚本将自动写入三大领域的完整本体数据（幂等操作，可安全重复运行）：

| 领域 | 实体数 | 关系数 | 覆盖范围 |
| :--- | :--- | :--- | :--- |
| 🌍 地缘政治 (Geopolitics) | 60+ | 130+ | 国家、领导人、军事联盟、代理冲突、制裁 |
| 🤖 科技/AI (Tech / AI)   | 55+ | 100+ | AI公司、模型、算力基础设施、出口管制 |
| 💰 经济 (Economy)         | 35+ | 70+  | 贸易、能源、供应链、金融市场 |

**必含高频新闻关系示例：**
- `US --strategic_rival--> Iran` (strength 0.90)
- `Israel --military_strike--> Hezbollah` (strength 0.90)
- `Iran --controls--> Strait_of_Hormuz` (strength 0.90)
- `AI_Model --causes--> Job_Displacement` (strength 0.85)
- `Data_Center --consumes--> Energy` (strength 0.90)
- `WTO --regulates--> Trade` (strength 0.90)
- `Oil --flows_through--> Strait_of_Hormuz` (strength 0.90)

运行后系统会打印统计摘要，例如：
```
======================================================================
🎯 SEED ONTOLOGY COMPLETE
======================================================================
📊 Inserted 167 nodes
🔗 Inserted 304 relationships
⏰ Timestamp: 2026-03-26T16:24:35
======================================================================
```

---

## 🤝 参与贡献 / Contributing

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request
