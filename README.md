<p align="center">
  <h1 align="center">Astrolabe</h1>
  <p align="center">
    <strong>Metadata reliability layer for AI-native data infrastructure</strong>
  </p>
  <p align="center">
    <em>The past is trustworthy. The present is clear.</em>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> &middot;
    <a href="#architecture">Architecture</a> &middot;
    <a href="#mcp-integration">MCP Integration</a> &middot;
    <a href="docs/">Documentation</a>
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
# Install
pip install -e ".[all]"

# Run MCP server
python -m xingtu_mcp.server

# Or use the CLI
xingtu --help
```

### Swift (macOS native app)

```bash
# Build
swift build

# Run CLI
swift run XingTuCLI

# Run GUI app
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
- macOS GUI (SwiftUI)             - Universe model (intent → delta)
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
   confidence >= 0.85 ?  ──yes──>  Auto-apply + log
        |
       no
        |
   confidence >= 0.50 ?  ──yes──>  Apply + queue for review
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

MIT

## Contributing

Contributions welcome. Please open an issue first to discuss what you would like to change.
