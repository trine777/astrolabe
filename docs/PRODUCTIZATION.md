# Astrolabe 产品化技术方案

## Context

Astrolabe (星图) 当前是一个 **元数据可靠层原型**，具备存储、搜索、信任评估、血缘关系的核心能力。

> **定位约束 (2026-04-29 修正)**: 主路径是 **Python lib import** (`from xingtu import XingTuService`)，REST/Docker 是**给跨语言客户端的 Adapter**，不是产品核心定位。详见 [`POSITIONING.md`](POSITIONING.md)。本方案的 Phase 0 是 Adapter 形态实施，**不强制**所有用户走这条路 — 同语言同进程的客户应直接 lib import。

本方案定义 Astrolabe Adapter 形态从原型到产品的完整技术路径，分 4 个 Phase 渐进交付，每个 Phase 独立可部署、独立可验证。

---

## Phase 0: Matrix REST Adapter (可选)

> 目标：让星图除了 "Python 库" 形态外，也能 "作为 REST 服务被 Matrix (Go) 等跨语言客户端调用"。
>
> **谁需要这条路径**: Matrix Go / 浏览器 / TypeScript / 任何非同进程 Python 客户端。
> **谁不需要**: FYD 等同进程 Python 项目 — 直接 lib import。

### 0.1 HTTP API 网关

**现状**：entrypoint.py 是 `while True: sleep(3600)`，MCP 仅支持 stdio。

**方案**：新增 `src/xingtu_api/` 模块，基于 FastAPI，与 MCP server 共享 `XingTuService` 实例。

```
src/
  xingtu_api/
    __init__.py
    main.py          # FastAPI app, uvicorn entry
    routes/
      collections.py # REST: /api/v1/collections
      documents.py   # REST: /api/v1/documents
      search.py      # REST: /api/v1/search
      trust.py       # REST: /api/v1/trust
      ingest.py      # REST: /api/v1/ingest  (excel, database, file)
    middleware/
      auth.py        # 认证中间件
      tenant.py      # 租户上下文注入
    deps.py          # FastAPI dependencies (get_service, get_tenant)
```

**关键设计**：
- HTTP API 与 MCP tools **1:1 映射**，不引入额外抽象
- MCP server 和 HTTP server 可以独立运行，也可以同进程
- Docker 内默认启动 HTTP server（端口 8000），MCP 作为可选 sidecar

**文件改动**：
- 新增 `src/xingtu_api/` 目录
- 修改 `entrypoint.py` → 启动 uvicorn
- 修改 `Dockerfile` CMD → `uvicorn xingtu_api.main:app`
- 修改 `pyproject.toml` → 加 `fastapi`, `uvicorn` 依赖

### 0.2 多租户隔离

**现状**：所有模型无 `tenant_id`，全局共享。

**方案**：所有核心模型（Collection, Document, Relation, Event）加 `tenant_id` 字段。

```python
# models.py — 4 个模型统一加字段
class Collection(LanceModel):
    tenant_id: str = Field(default="default", description="租户 ID / Area ID")
    ...

class Document(LanceModel):
    tenant_id: str = Field(default="default", description="租户 ID / Area ID")
    ...
```

**隔离策略**：
- 所有 store.py 查询方法加 `tenant_id` 过滤条件
- MCP / HTTP API 层通过 `tenant_id` 参数或 Header (`X-Tenant-ID`) 传入
- Matrix Agent 调用时透传 `area_id` 作为 `tenant_id`
- `tenant_id="default"` 保持向后兼容

**文件改动**：
- `src/xingtu/models.py` — 4 个 LanceModel 加字段
- `src/xingtu/store.py` — 所有查询方法加 tenant_id 过滤
- `src/xingtu/__init__.py` — 服务层透传
- `src/xingtu_mcp/server.py` — 工具加可选 tenant_id 参数
- `src/xingtu_api/middleware/tenant.py` — HTTP 中间件提取 tenant

### 0.3 认证

**方案**：轻量 API Key 认证，与 Matrix 的 `X-Caller-ID` 对齐。

```python
# middleware/auth.py
# 两种模式：
# 1. API Key (Header: Authorization: Bearer <key>)
# 2. Matrix 透传 (Header: X-Caller-ID: <agent_id>)
# 配置 XINGTU_AUTH_MODE=apikey|matrix|none
```

**文件改动**：
- 新增 `src/xingtu_api/middleware/auth.py`
- `src/xingtu/config.py` — 加 AuthConfig

### 0.4 Docker Compose 产品化

```yaml
services:
  astrolabe:
    build: .
    ports: ["8000:8000"]
    environment:
      - XINGTU_AUTH_MODE=matrix
      - XINGTU_EMBEDDING_PROVIDER=openai
    volumes:
      - astrolabe-data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]

volumes:
  astrolabe-data:
```

---

## Phase 1: 资产目录 (registry)

> 目标：让星图从"元数据存储"升级为"数据资产目录"，对齐 Matrix data-governance Room 的 `register_asset` 需求

### 1.1 资产卡片 (Asset Card)

**现状**：Collection 只有 name/description/tags，无标准化的资产描述。

**方案**：新增 `AssetCard` 模型，作为 Collection 的扩展元数据。

```python
class AssetCard(BaseModel):
    """数据资产卡片 — 标准化的资产描述"""
    asset_id: str                    # = collection_id
    domain: str                      # 业务域 (finance, marketing, operations)
    owner: str                       # 资产所有者
    sensitivity: str                 # public | internal | confidential | restricted
    update_frequency: Optional[str]  # daily | weekly | manual | event-driven
    schema_summary: dict             # {field_name: field_type} 摘要
    quality_score: float             # 0-1, 从 trust 评估聚合
    row_count: int                   # 数据行数
    freshness_hours: Optional[float] # 距上次更新的小时数
    sla: Optional[str]              # 服务等级 (e.g. "99.9% available, <1h delay")
    tags: List[str]                  # 标准化标签
    lineage_upstream: List[str]      # 上游资产 ID
    lineage_downstream: List[str]    # 下游资产 ID
    created_at: str
    updated_at: str
```

**存储方式**：序列化为 JSON 存入 `Collection.metadata_json`，不新增表。

**MCP 工具**：
- `xingtu_register_asset(collection_id, domain, owner, sensitivity, ...)` — 注册/更新资产卡片
- `xingtu_get_asset_card(collection_id)` — 获取资产卡片
- `xingtu_search_assets(domain, sensitivity, min_quality, ...)` — 按 facet 搜索资产

### 1.2 Schema Registry

**现状**：文档 schema 是隐含的，无法查询"这个集合有哪些字段"。

**方案**：导入时自动推断 schema，持久化到 AssetCard.schema_summary。

```python
# ingest.py — CSV/Excel/DB 导入时自动提取
def _extract_schema(columns: List[str], sample_rows: List[dict]) -> dict:
    """推断字段类型：string, integer, float, datetime, boolean"""
    schema = {}
    for col in columns:
        values = [r.get(col) for r in sample_rows[:100] if r.get(col) is not None]
        schema[col] = _infer_type(values)
    return schema
```

### 1.3 使用统计

**现状**：Event 表记录了 `searched` 事件但无聚合统计。

**方案**：新增 MCP 工具 `xingtu_get_asset_usage(collection_id)` 聚合 Event 表：
- 查询次数（按天/周/月）
- 最近访问者列表
- 最热门搜索词

---

## Phase 2: 数据生命周期 (volume)

> 目标：生产环境的数据安全与可运维性

### 2.1 版本快照

**方案**：Collection 加 `version` 字段，变更时自动递增。

```python
# store.py — update_collection 时
def update_collection(self, id, **kwargs):
    existing = self.get_collection(id)
    kwargs["version"] = existing.get("version", 0) + 1
    # 可选：保存旧版本快照到 events 表
    ...
```

**MCP 工具**：`xingtu_snapshot_collection(id)` — 冻结当前状态，写入 Event 的 `before_snapshot`。

### 2.2 数据留存策略

**方案**：配置化 TTL，后台定时清理。

```python
# config.py
class LifecycleConfig(BaseModel):
    event_ttl_days: int = 90        # Event 保留天数
    memory_ttl_days: int = 30       # Agent 记忆 TTL
    optimize_interval_hours: int = 24
```

新增 `src/xingtu/worker.py` — 后台任务：
- 定时 `optimize()`
- TTL 清理过期 Event / Memory
- 存储用量统计 + 告警

### 2.3 备份与导出

**MCP 工具**：
- `xingtu_export_collection(id, format="csv|json|parquet")` — 导出集合数据
- `xingtu_backup(path)` — 快照整个 LanceDB 目录
- `xingtu_restore(path)` — 从快照恢复

### 2.4 存储配额

**方案**：per-tenant 配额，存储在 config 或单独配额表。

```python
class TenantQuota(BaseModel):
    tenant_id: str
    max_collections: int = 100
    max_documents: int = 1_000_000
    max_storage_mb: int = 10_000
```

超配额时 `add_documents` / `ingest_*` 返回错误而非静默失败。

---

## Phase 3: 事件通信 (network)

> 目标：星图从"被动查询"升级为"主动通知"，融入 Matrix 的 Flow 事件流

### 3.1 Webhook 事件推送

**现状**：Event 表只能拉取，无推送机制。

**方案**：新增 Webhook 注册机制。

```python
# 新增 MCP 工具
xingtu_register_webhook(
    tenant_id: str,
    event_types: List[str],    # ["created", "updated", "trust_changed"]
    target_url: str,           # Matrix Flow 触发端点
    secret: str,               # HMAC 签名密钥
)
```

**事件流**：
```
Document 写入 → Event 记录 → 匹配 Webhook 规则 → POST target_url
                                                    ↓
                                            Matrix Area Flow 触发
                                                    ↓
                                            下游 Room 创建 Task
```

**关键设计**：
- Webhook 投递是 fire-and-forget + 重试（3 次，指数退避）
- 需要 `worker.py` 后台消费事件队列
- 初期用内存队列，后续可切换 Redis

### 3.2 变更数据捕获 (CDC)

**前瞻性设计**：当数据资产的底层数据发生变更时，星图应能感知并更新信任分。

```python
# 新增 MCP 工具
xingtu_notify_data_change(
    collection_id: str,
    change_type: str,          # "schema_change" | "data_refresh" | "quality_degradation"
    details: dict,             # 变更详情
)
```

收到通知后星图自动：
1. 重算该 Collection 的 trust_score
2. 更新 AssetCard.freshness_hours
3. 触发已注册的 Webhook

### 3.3 Matrix Flow 集成

**设计**：星图作为 Area MCP 被挂载后，可以成为 Flow 的触发源。

```
data-intake Room 完成 → artifact 提交
    ↓
Agent 调用 xingtu_ingest_excel(file) + xingtu_register_asset(...)
    ↓
星图写入 Event(type=created, target_type=document)
    ↓
Webhook 推送到 Matrix: POST /api/area/{area_id}/trigger-flow
    ↓
Matrix 自动创建 data-governance Task (type=register_asset)
```

---

## Phase 4: 导航引擎 (GPS 核心)

> 前瞻性设计：对齐 KERNEL.md v1.0.1 的完整对象模型。当前 Phase 不实现，但架构预留。

### 4.1 当前模型 vs KERNEL 模型差距

| KERNEL 定义 | 当前实现 | 差距 |
|------------|---------|------|
| **Modality** (原子元数据单元) | Document | 基本对齐，缺 facet_type |
| **Facet** (认知面：capability/governance/quality/...) | 无 | 完全缺失 |
| **Profile** (完整画像 = 所有 Facet + ProfileTrust) | Collection + trust_score | 结构不同 |
| **Topology** (NavigableEdge vs DiscoveryEdge) | Relation (无 edge 类型区分) | 需拆分 |
| **Vision** (目标声明) | UniverseGoal | 字段不完整 |
| **ExecutionPosition** (运行时快照) | 无 | 完全缺失 |
| **Route** (路由 = Waypoint[] + trust_floor) | 无 | 完全缺失 |
| **Directive** (执行指令合约) | 无 | 完全缺失 |
| **Trail** (跨会话足迹) | 无 | 完全缺失 |
| **Drift** (偏航检测) | 无 | 完全缺失 |

### 4.2 架构预留

Phase 0-3 的设计应为 Phase 4 预留扩展点：

**Relation 表预留**：
```python
class Relation(LanceModel):
    edge_class: str = Field(default="discovery",
        description="navigable | discovery — KERNEL §4.3")
    # navigable: 参与路由规划
    # discovery: 仅供发现，不参与导航
```

**Document 表预留**：
```python
class Document(LanceModel):
    facet_type: Optional[str] = Field(default=None,
        description="capability | governance | quality | ... — KERNEL §3.2")
    profile_id: Optional[str] = Field(default=None,
        description="所属 Profile ID — KERNEL §3.3")
```

**Event 表预留 Trail**：
```python
# Trail 可以通过 Event 表的 actor_id + target_id 聚合构造
# 不需要新增表，但需要新增 event_type: "trail_recorded"
```

### 4.3 渐进路径

```
Phase 0-1 (现在):
  Document = 扁平文档，无 Facet 概念
  Relation = 统一关系，无 edge_class 区分
  Trust = 5 维评分，与 KERNEL 的 ProfileTrust 3 维 + AgentAccessScore 2 维 不对齐

Phase 2-3 (3 个月后):
  Document 开始标记 facet_type
  Relation 区分 navigable / discovery
  Trust 拆分为 ProfileTrust + AgentAccessScore

Phase 4 (6 个月后):
  Profile 聚合多个 Facet
  Route 规划 (基于 Topology 的 NavigableEdge)
  Directive 生成 (基于 Route + ExecutionPosition)
  Drift 检测 (轮询 ExecutionPosition vs Route.current_waypoint)
  Trail 持久化 (跨会话足迹)
```

---

## 交付里程碑

| Phase | 交付物 | 验证方式 | 预计 |
|-------|--------|---------|------|
| **Phase 0** | HTTP API + 多租户 + 认证 + Docker | `curl /health` + 跨租户隔离测试 | 先做 |
| **Phase 1** | 资产卡片 + Schema Registry + 使用统计 | data-governance Room 调用 `register_asset` 闭环 | 紧跟 |
| **Phase 2** | 版本快照 + TTL + 备份导出 + 配额 | `backup` → 删除 → `restore` 验证 | 稳定后 |
| **Phase 3** | Webhook + CDC + Matrix Flow 集成 | intake → 星图写入 → Webhook → governance Room 自动触发 | 联调 |
| **Phase 4** | Facet/Profile/Route/Directive/Trail | 完整 GPS 导航闭环 | 远期 |

## 关键文件清单

| 文件 | 改动类型 | Phase |
|------|---------|-------|
| `src/xingtu/models.py` | 修改：加 tenant_id, edge_class, facet_type 预留字段 | 0 |
| `src/xingtu/store.py` | 修改：所有查询加 tenant_id 过滤 | 0 |
| `src/xingtu/__init__.py` | 修改：服务层透传 tenant_id | 0 |
| `src/xingtu/config.py` | 修改：加 AuthConfig, LifecycleConfig | 0+2 |
| `src/xingtu_mcp/server.py` | 修改：工具加 tenant_id 参数 | 0 |
| `src/xingtu_api/` | **新增**：FastAPI HTTP 服务 | 0 |
| `src/xingtu_api/middleware/auth.py` | **新增**：认证中间件 | 0 |
| `src/xingtu_api/middleware/tenant.py` | **新增**：租户中间件 | 0 |
| `src/xingtu/asset.py` | **新增**：AssetCard 模型 + 注册/搜索 | 1 |
| `src/xingtu/worker.py` | **新增**：后台任务 (TTL/optimize/webhook) | 2+3 |
| `src/xingtu/webhook.py` | **新增**：Webhook 注册 + 投递 | 3 |
| `Dockerfile` | 修改：CMD → uvicorn | 0 |
| `docker-compose.yml` | 修改：ports + healthcheck | 0 |
| `pyproject.toml` | 修改：加 fastapi, uvicorn 依赖 | 0 |
| `Tests/test_api.py` | **新增**：HTTP API 测试 | 0 |
| `Tests/test_tenant.py` | **新增**：多租户隔离测试 | 0 |
| `Tests/test_asset.py` | **新增**：资产卡片测试 | 1 |

## 验证方案

### Phase 0 验证
```bash
# 1. 构建 + 启动
docker compose up -d

# 2. 健康检查
curl http://localhost:8000/health

# 3. 多租户隔离
curl -H "X-Tenant-ID: area-smart-data" POST /api/v1/collections ...
curl -H "X-Tenant-ID: area-defi" POST /api/v1/collections ...
# 验证 area-smart-data 看不到 area-defi 的数据

# 4. Matrix 挂载
POST /api/area/{area_id}/mount-mcp
  { "mcp_key": "astrolabe", "mcp_type": "http", "endpoint": "http://astrolabe:8000" }

# 5. 运行测试
python3 -m pytest Tests/ -v
```

### Phase 1 验证
```bash
# Agent 在 data-governance Room 中调用
xingtu_register_asset(collection_id, domain="finance", owner="data-team", ...)
xingtu_search_assets(domain="finance", min_quality=0.8)
xingtu_get_asset_card(collection_id)
```

### Phase 3 验证
```
data-intake Room → Agent 调用 xingtu_ingest_excel → Event 写入
  → Webhook POST Matrix /trigger-flow
  → data-governance Room 自动创建 register_asset Task
```
