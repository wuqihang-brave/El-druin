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

首次启动后，**推荐运行一次**以下命令初始化 KuzuDB 本体数据，获得包含地缘政治、科技/AI、经济三大领域的丰富本体（157 个实体，331 条高质量关系）：

```bash
python -m backend.knowledge_layer.seed_ontology
```

运行后输出示例：

```
Inserted 157 nodes and 331 relationships
```

涵盖的典型关系：
- `US --strategic_rival→ Iran / China / Russia`
- `Israel --military_strike→ Iran / Lebanon / Hezbollah`
- `Iran --controls→ Strait_of_Hormuz`
- `AI_model --causes→ job_displacement`
- `Data_Center --consumes→ Energy`
- `Supply_Chain --vulnerable_to→ Geopolitical_Risk`

---

## 📚 导入 Schema.org 本体类型层次 / Import Schema.org Ontology

为了让知识图谱的上下文提取在实体边数为零时仍能提供类型级别的语义背景，
本项目内置了 schema.org 完整类型层次（`backend/ontology/resources/schemaorg_nodes.json`，约 1466 个类型）。

### 一次性导入

```bash
# 从项目根目录执行（确保已安装 kuzu）：
python -m backend.ontology.tools.import_schemaorg

# 指定自定义 DB 路径：
python -m backend.ontology.tools.import_schemaorg --db ./data/el_druin.kuzu

# 仅导入前 100 个类型（测试用）：
python -m backend.ontology.tools.import_schemaorg --limit 100

# 重置后重新导入（删除旧表再写入）：
python -m backend.ontology.tools.import_schemaorg --reset
```

导入后效果：
- Kuzu DB 中新增 `SchemaType` 节点表（~1466 个类型节点）和 `SUBTYPE_OF` 关系表（~996 条边）
- 当实体（如 "Ryder Cup", "Tiger Woods"）在 KG 中无直接关系时，上下文提取器自动回退到 schema.org 类型层次，提供最小可用的类型级背景
- 日志将显示 `KG fallback – using schema.org type-hierarchy context` 而非 `0 1-hop + 0 2-hop`

### 重新生成 schemaorg_nodes.json

如果需要从最新的 schema.org CSV 重新生成 JSON：

```bash
# 下载最新 CSV 并放置到：
# backend/ontology/resources/schemaorg-current-https-types.csv
# 然后运行：
python tools/generate_schemaorg_ontology.py
```

---

## 🔬 本体代数验证 / Ontology Algebra Validation

`backend/ontology/relation_schema.py` 实现了基于群论的关系代数验证：

- **逆元一致性**：若模式 A 的逆是 B，则 B 的逆必须是 A。通过 `validate_inverses()` 静态检查。
- **组合闭包**：`composition_table` 定义了两个模式合成后的高阶效应（Cayley Table），通过 `validate_composition_closure()` 验证引用完整性。
- **未知实体类型短路**：当实体类型无法推断（返回 `"unknown"`）时，笛卡尔积匹配自动跳过，避免污染推演结果。

应用启动时自动在非严格模式下运行验证（仅记录警告）。在开发环境中启用严格模式：

```bash
DEBUG=true uvicorn app.main:app --reload --port 8001
```

手动运行验证：

```python
from ontology.relation_schema import run_ontology_validation
run_ontology_validation(strict=False)  # 生产模式：只警告
run_ontology_validation(strict=True)   # 开发模式：有错误时抛出 ValueError
```

---

## 🤝 参与贡献 / Contributing

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request
