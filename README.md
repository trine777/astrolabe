<p align="center">
  <h1 align="center">Astrolabe</h1>
  <p align="center">
    <strong>Metadata reliability layer for AI-native data infrastructure</strong><br>
    <strong>面向 AI 原生数据基建的元数据可靠层</strong>
  </p>
  <p align="center">
    <em>The past is trustworthy. The present is clear.</em><br>
    <em>过去可信，当下清晰。</em>
  </p>
  <p align="center">
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
    <a href="https://www.swift.org/"><img src="https://img.shields.io/badge/swift-5.9+-orange.svg" alt="Swift 5.9+"></a>
    <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-green.svg" alt="MCP Compatible"></a>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> &middot;
    <a href="#architecture">Architecture</a> &middot;
    <a href="#mcp-integration">MCP Integration</a> &middot;
    <a href="docs/">Docs</a> &middot;
    <a href="#中文说明">中文</a>
  </p>
</p>

---

## What is Astrolabe?

Astrolabe is a **metadata reliability layer** that sits between your data infrastructure and AI agents. It answers one question: **is the metadata trustworthy?**

- **Track provenance** &mdash; who said what, when, based on what evidence
- **Maintain freshness** &mdash; detect when metadata goes stale as underlying data changes
- **Audit everything** &mdash; atomic mutation + audit in a single transaction
- **Human-AI collaboration** &mdash; AI infers metadata, humans confirm; progressive trust

```
Data Infrastructure (lakes, warehouses, pipelines)
        |
        v  schema change events, data quality signals
   Astrolabe (metadata reliability layer)
        |
        v  trusted metadata + trust_score
   AI Agents / Decision Systems
```

## Key Features

| Feature | Description |
|---------|-------------|
| **AI-driven inference** | Automatic semantic type detection with confidence scoring |
| **Progressive trust** | Configurable auto-apply thresholds; low-confidence decisions queue for human review |
| **Atomic audit trail** | Every metadata mutation is recorded in the same transaction |
| **MCP Server** | AI agents (Claude, etc.) access metadata via [Model Context Protocol](https://modelcontextprotocol.io) |
| **Dual interface** | macOS native GUI for humans, MCP for AI &mdash; shared metadata store |
| **Multi-modal search** | Vector, full-text, and hybrid search over documents and metadata |
| **Event-driven** | File drop triggers auto-import, inference, relation discovery |
| **Docker-ready** | Single `docker compose up` for the Python stack |

## Quick Start

### Python (metadata engine + MCP server)

```bash
pip install -e ".[all]"

# Run MCP server
python -m xingtu_mcp.server

# Or use the CLI
xingtu --help
```

### Load the built-in maps (推荐, agent 友好)

两份操作地图，让 agent 加载即知怎么用：

```bash
# Matrix 操作地图 (7 area / 11 room / 19 op / 42 docs) —— 外部 Matrix 系统的导航
python3 scripts/import_matrix_map.py

# 星图自述地图 (5 area / 8 organ / 19 op) —— 本系统自己能做什么
python3 scripts/import_xingtu_map.py
```

调用：
```python
from xingtu import XingTuService
svc = XingTuService(); svc.initialize()
svc.matrix_map.overview()                            # 全图概览
svc.matrix_map.find("discussion")                    # 关键词搜
svc.matrix_map.get_operation("op-create-discussion") # 完整 curl + 规则
```

详见 [`docs/matrix-map/README.md`](docs/matrix-map/README.md) 和 [`docs/xingtu-map/README.md`](docs/xingtu-map/README.md)。

### Swift (macOS native app)

```bash
swift build
swift run XingTuCLI
swift run XingTuApp
```

### Docker

```bash
cp .env.example .env
# Edit .env with your API keys
docker compose up -d
```

## Architecture

Astrolabe has two stacks serving different roles:

```
Swift / SQLite                    Python / LanceDB
─────────────────                 ─────────────────
Metadata source of truth          Retrieval & AI infrastructure
- MetaStore (CRUD)                - Vector search
- Atomic audit (transactions)     - Embedding management
- Review queue (persistent)       - Multi-modal ingest
- AI decision log (persistent)    - MCP server
- macOS GUI (SwiftUI)             - Universe model (intent -> delta)
```

### Core Components

| Component | Role | Module |
|-----------|------|--------|
| **Xingkongzuo** (MetaStore) | Metadata CRUD + audit | `Sources/XingTu/Xingkongzuo/` |
| **Yujieshu** (Ingest) | Multi-format data import | `src/xingtu/ingest.py` |
| **Yinglanxuan** (Events) | Event stream + audit log | `Sources/XingTu/EventDriven/` |
| **Chixinhe** (Search) | Vector/text/hybrid search | `src/xingtu/search.py` |
| **Decision Manager** | AI decision processing + persistence | `Sources/XingTu/Decision/` |
| **Review Queue** | Human review of AI decisions | `Sources/XingTu/Decision/` |

### Metadata Reliability Model

Every piece of metadata carries reliability signals:

```
trust_score = f(provenance, freshness, confidence, human_confirmed)
```

| Signal | Source | Stored in |
|--------|--------|-----------|
| **Confidence** | AI inference (0.0 - 1.0) | `ai_decisions.confidence` |
| **Human confirmation** | Review queue approval | `meta_properties.user_confirmed_at` |
| **Provenance** | Who created/modified, when | `meta_events` (atomic audit) |
| **Freshness** | Last validated timestamp | `meta_properties.updated_at` |

### Decision Flow

```
AI Agent infers metadata
        |
        v
   confidence >= 0.85 ?  --yes-->  Auto-apply + log
        |
       no
        |
   confidence >= 0.50 ?  --yes-->  Apply + queue for review
        |
       no
        v
   Queue for human review only
```

## MCP Integration

Astrolabe exposes metadata operations via MCP, letting AI agents:

```yaml
tools:
  - xingtu_import_csv        # Import data files
  - xingtu_list_objects       # Browse metadata
  - xingtu_infer_semantics    # AI semantic inference
  - xingtu_get_review_queue   # Check pending reviews
  - xingtu_query_data         # Query with natural language
  - xingtu_get_world_model    # Full metadata context
```

Configure in your MCP client:

```json
{
  "mcpServers": {
    "xingtu": {
      "command": "python",
      "args": ["-m", "xingtu_mcp.server"],
      "env": {
        "XINGTU_DB_PATH": "~/.xingtu/data",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

## Project Structure

```
astrolabe/
├── Sources/                    # Swift (metadata source of truth)
│   ├── XingTu/                 # Core library
│   │   ├── Storage/            #   SQLite manager (v1 + v2 tables)
│   │   ├── Xingkongzuo/        #   MetaStore (CRUD + atomic audit)
│   │   ├── Decision/           #   AI decisions + review queue
│   │   ├── EventDriven/        #   Event bus + scheduler
│   │   ├── Models/             #   MetaObject, MetaProperty, MetaRelation
│   │   ├── Core/               #   CSV parser, AI service
│   │   └── XingJi/             #   Auto-import, semantic inference
│   ├── XingTuApp/              # macOS GUI (SwiftUI)
│   └── XingTuCLI/              # Command-line interface
├── src/                        # Python (retrieval + AI)
│   ├── xingtu/                 #   Core: store, search, models, ingest
│   ├── xingtu_mcp/             #   MCP server
│   └── xingtu_cli/             #   CLI
├── docs/                       # Design documents
├── cells/                      # Cell definitions (YAML)
├── xingji/                     # Xingji definitions (YAML)
├── Dockerfile                  # Docker build
├── docker-compose.yml          # Docker deployment
├── Package.swift               # Swift package manifest
└── pyproject.toml              # Python package manifest
```

## Database Schema

### v1 Tables (metadata core)

| Table | Purpose |
|-------|---------|
| `meta_objects` | Data source objects (CSV files, tables, etc.) |
| `meta_properties` | Column/field metadata with semantic types |
| `meta_relations` | Relationships between data sources |
| `meta_events` | Audit trail (atomic with mutations) |
| `metric_defs` | Business metric definitions |

### v2 Tables (AI + event-driven)

| Table | Purpose |
|-------|---------|
| `events` | Event bus persistence (full payload) |
| `ai_decisions` | AI decision log with confidence + status |
| `review_queue` | Human review items with expiration |
| `xingji_executions` | Execution records for automated workflows |

## Configuration

Environment variables (see [`.env.example`](.env.example)):

| Variable | Default | Description |
|----------|---------|-------------|
| `XINGTU_DB_PATH` | `~/.xingtu/data` | LanceDB data directory |
| `XINGTU_EMBEDDING_PROVIDER` | `openai` | `openai` / `ollama` / `sentence-transformers` |
| `OPENAI_API_KEY` | &mdash; | Required for OpenAI embeddings |
| `XINGTU_LOG_LEVEL` | `INFO` | Logging level |

## Requirements

- **Swift**: macOS 14+, Swift 5.9+
- **Python**: 3.9+
- **Dependencies**: LanceDB, PyArrow, Pydantic (Python); SQLite.swift (Swift)

## License

This project is licensed under the **MIT License** &mdash; see the [LICENSE](LICENSE) file for details.

You are free to use, modify, and distribute this software for any purpose, including commercial use, provided the original copyright notice and license are included.

## Contributing

Contributions are welcome. Please open an issue first to discuss what you would like to change.

---

<a id="中文说明"></a>

## 中文说明

### 什么是 Astrolabe（星盘）？

Astrolabe 是一个**元数据可靠层**，位于数据基建（数据湖、数据仓库、数据管道）与 AI Agent 之间。它回答一个核心问题：**元数据是否可信？**

```
数据基建（数据湖 / 数据仓库 / 数据管道）
        │
        ▼  schema 变更事件、数据质量信号
   Astrolabe（元数据可靠层）
        │
        ▼  可信元数据 + 信任分
   AI Agent / 上层决策系统
```

### 设计理念

> 过去是可信的（数据可靠）&mdash; 星图主力<br>
> 现在是明确的（意图清晰）&mdash; 星图补充

星图不做路线规划、不做未来预测。它的核心职责是：**确保元数据可追溯、可信赖、可审计**。

### 核心能力

| 能力 | 说明 |
|------|------|
| **AI 语义推断** | 自动检测字段语义类型，附带置信度评分 |
| **渐进信任** | 可配置的自动应用阈值；低置信度决策排队等待人工审核 |
| **原子审计** | 每次元数据变更与审计日志在同一事务中完成 |
| **MCP 接口** | AI Agent（Claude 等）通过 [Model Context Protocol](https://modelcontextprotocol.io) 访问元数据 |
| **双界面** | macOS 原生 GUI 供人类使用，MCP 供 AI 使用 &mdash; 共享同一元数据存储 |
| **多模态搜索** | 向量搜索、全文检索、混合搜索 |
| **事件驱动** | 文件拖入自动触发导入、推断、关系发现 |
| **Docker 部署** | 一键 `docker compose up` |

### 元数据可靠性模型

每条元数据携带可靠性信号：

```
信任分 = f(溯源, 新鲜度, 置信度, 人工确认)
```

| 信号 | 来源 | 存储位置 |
|------|------|----------|
| **置信度** | AI 推断 (0.0 - 1.0) | `ai_decisions.confidence` |
| **人工确认** | 审核队列通过 | `meta_properties.user_confirmed_at` |
| **溯源** | 谁创建/修改，何时 | `meta_events`（原子审计） |
| **新鲜度** | 最近验证时间戳 | `meta_properties.updated_at` |

### 双技术栈

| 栈 | 角色 | 技术 |
|----|------|------|
| **Swift** | 元数据真相源 | SQLite、SwiftUI、原子事务 |
| **Python** | 检索与 AI 基础设施 | LanceDB、PyArrow、向量搜索 |

### 快速开始

```bash
# Python
pip install -e ".[all]"
python -m xingtu_mcp.server

# Swift
swift build
swift run XingTuApp

# Docker
cp .env.example .env
docker compose up -d
```

### 开源协议

本项目采用 **MIT 许可证** 开源 &mdash; 详见 [LICENSE](LICENSE) 文件。

你可以自由地使用、修改和分发本软件（包括商业用途），前提是保留原始版权声明和许可证。

### 参与贡献

欢迎贡献代码。请先开 Issue 讨论你想要做的变更。
