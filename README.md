# 知识库智能问答系统

一个面向企业文档的 RAG（检索增强生成）知识问答系统。支持把企业规章、运维手册等文档按知识库分类导入，基于本地向量模型检索、交叉编码器重排，再由 DeepSeek 大模型依据检索到的资料生成带出处的回答，并提供多轮会话记忆、文档与问答对管理、媒体附件等能力。

## 功能特性

- **多知识库隔离**：按业务分类（如公司规章、公司运维、财务报销等）建立独立知识库，每个知识库对应独立的向量集合，互不干扰。
- **RAG 问答链路**：基于 LangGraph 状态图编排「知识库校验 → 向量召回 → 交叉编码器重排 → LLM 生成 → 来源汇总」，检索与生成可独立评测。
- **引用与拒答**：回答严格依据检索资料，标注命中文档来源；资料缺失时明确回答"根据已有资料无法回答"，不编造。
- **多轮会话记忆**：会话与消息持久化，续聊时自动注入历史，回答取决于会话绑定的知识库。
- **文档与问答管理**：支持上传 `.txt` / `.md`，按 `Q:` / `A:` 格式解析为问答对，可在界面上增删改查。
- **媒体附件**：问答对可关联图片附件，作为回答的佐证材料随结果返回展示。
- **权限体系**：基于 JWT 的登录认证，区分普通用户 / 编辑 / 管理员角色，用户管理仅限管理员。
- **检索评测**：内置检索层与生成层评测 harness，可固化基线、对比每次优化，避免"假优化"。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | FastAPI、LangChain、LangGraph、ChromaDB、SQLite |
| 模型 | DeepSeek（生成）、bge-small-zh-v1.5（向量化）、bge-reranker-base（重排） |
| 前端 | React 19、TypeScript、Vite、Tailwind CSS 4 |

## 目录结构

```
KnowledgeBase/
├── backend/                 # 后端服务
│   ├── src/
│   │   ├── agent/           # RAG 问答链路（LangGraph 状态图 + DeepSeek）
│   │   ├── auth/            # 认证与用户管理（JWT）
│   │   ├── conversation/    # 会话与消息持久化
│   │   ├── document/        # 知识库 / 文档 / 问答对 / 媒体管理
│   │   ├── config.py        # 全局配置（.env 路径、应用数据库）
│   │   └── main.py          # 应用入口与 lifespan 启动预热
│   ├── eval/                # 检索层 / 生成层评测 harness 与报告
│   ├── requirements/        # 依赖清单（base / dev）
│   ├── docs/                # 示例知识文档（按分类）
│   ├── models/              # 本地模型（已忽略，需自行下载）
│   ├── data/                # 运行时数据（已忽略，启动自动生成）
│   └── .env.example         # 环境变量模板
├── frontend/                # 前端应用
│   └── src/                 # api / auth / chat / document / components
└── .gitignore
```

## 快速开始

### 前置要求

- Python 3.13+
- Node.js 18+ 与 npm
- DeepSeek API Key（[申请地址](https://platform.deepseek.com)）

### 1. 后端

```bash
cd backend

# 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 安装依赖
pip install -r requirements/base.txt
```

### 2. 下载本地模型

向量化与重排模型体积较大（合计约 1.2GB），未纳入版本控制，需自行下载到 `backend/models/` 下。任选一种方式：

**方式 A：ModelScope（国内推荐）**

```bash
pip install modelscope
modelscope download --model BAAI/bge-small-zh-v1.5  --local_dir backend/models/bge-small-zh-v1.5
modelscope download --model BAAI/bge-reranker-base --local_dir backend/models/bge-reranker-base
```

**方式 B：HuggingFace 镜像**

```bash
set HF_ENDPOINT=https://hf-mirror.com   # Windows（macOS/Linux 用 export）
huggingface-cli download BAAI/bge-small-zh-v1.5  --local-dir backend/models/bge-small-zh-v1.5
huggingface-cli download BAAI/bge-reranker-base --local-dir backend/models/bge-reranker-base
```

下载完成后在 `.env` 中把 `EMBEDDING_MODEL` 指向本地目录（见下节）。若跳过本地模型，直接使用模型名，首次运行会自动从 HuggingFace 下载。

### 3. 配置环境变量

```bash
cd backend
Copy-Item .env.example .env      # Windows
# cp .env.example .env           # macOS / Linux
```

编辑 `backend/.env`，至少需要填写：

- `JWT_SECRET_KEY`：随机字符串，生成 `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `USERS`：初始管理员，密码哈希用 `python -c "from src.auth.service import hash_password; print(hash_password('你的密码'))"` 生成
- `DEEPSEEK_API_KEY`：DeepSeek 平台申请的密钥
- `EMBEDDING_MODEL`：本地模型目录绝对路径，例如 `E:\myProject\KnowledgeBase\backend\models\bge-small-zh-v1.5`

### 4. 启动后端

```bash
# 在 backend/ 目录下执行
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

启动时会自动建表、做向量库一致性自检、预热 LLM 链与重排模型。控制台会打印各阶段进度日志，健康检查见 `http://127.0.0.1:8000/health`，接口文档见 `http://127.0.0.1:8000/docs`。

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。前端开发服务器已配置代理，将 `/auth`、`/agent`、`/document`、`/conversation`、`/health` 转发到后端 `127.0.0.1:8000`，无需额外配置 CORS。

## 配置项说明

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `JWT_SECRET_KEY` | 是 | — | JWT 签名密钥 |
| `JWT_ALGORITHM` | 否 | `HS256` | 签名算法 |
| `JWT_EXPIRE_MINUTES` | 否 | `1440` | 令牌有效期（分钟） |
| `USERS` | 是 | — | 预置用户 JSON 数组（含密码哈希） |
| `DEEPSEEK_API_KEY` | 是 | — | DeepSeek API Key |
| `DEEPSEEK_MODEL` | 否 | `deepseek-flash` | 生成模型名 |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com` | DeepSeek 接口地址 |
| `EMBEDDING_MODEL` | 否 | `BAAI/bge-small-zh-v1.5` | 向量化模型名或本地路径 |
| `RETRIEVAL_K` | 否 | `2` | 每次喂给 LLM 的片段数 |
| `QUERY_USE_INSTRUCTION` | 否 | `false` | 查询侧是否加 bge 指令前缀 |
| `RERANK_ENABLED` | 否 | `true` | 是否开启交叉编码器重排 |
| `RERANK_MODEL` | 否 | `backend/models/bge-reranker-base` | 重排模型路径 |
| `RERANK_RECALL_K` | 否 | `10` | 重排前的召回候选数 |
| `APP_DB_PATH` | 否 | `backend/data/app.db` | SQLite 业务库路径 |
| `CHROMA_DIR` | 否 | `backend/data/chroma` | 向量库存储目录 |
| `MEDIA_ROOT` | 否 | `backend/data/media` | 媒体附件目录 |

## API 概览

所有业务接口需在请求头携带 `Authorization: Bearer <token>`。

| 分组 | 方法与路径 | 说明 |
| --- | --- | --- |
| 认证 | `POST /auth/login` | 登录获取令牌 |
| 认证 | `GET /auth/me` | 当前用户信息 |
| 认证 | `POST/GET/PUT/DELETE /auth/users` | 用户管理（仅管理员） |
| 问答 | `POST /agent/invoke` | RAG 问答（带 `conversation_id` 则续聊） |
| 文档 | `/document/knowledge-bases/**` | 知识库 / 文档 / 问答对 / 媒体管理 |
| 会话 | `GET/DELETE /conversation/conversations/**` | 会话历史查询与删除 |
| 系统 | `GET /health` | 健康检查（无需登录） |

## 评测

`backend/eval/` 内置评测 harness，跑分脚本调用生产检索唯一入口，保证评测与线上行为一致。

```bash
cd backend

# 检索层评测：固化基线 / 跑新配置 / 前后对比
python -m eval.run_retrieval_eval --tag baseline
python -m eval.run_retrieval_eval --tag v2 --k 6 --compare-with baseline

# 生成层评测（需额外安装 dev 依赖）
pip install -r requirements/dev.txt
python -m eval.run_answer_eval
```

历史评测结果保存在 `backend/eval/reports/`，根目录 `rag_eval_report.html` 为汇总报告。

## 注意事项

- **不要提交 `backend/.env`**：其中包含 JWT 密钥、用户密码哈希与 API Key，已通过 `.gitignore` 忽略；如曾误提交，请立即轮换密钥。
- `backend/models/` 与 `backend/data/` 不入库：前者体积过大需自行下载，后者为运行时数据、启动时自动生成。
- 本项目原使用 SVN 管理，`.svn/` 已被忽略，改用 Git 后不影响 SVN 的日常使用。