# Astrolabe (星图) — Agent 使用指引

## 定位

**元数据可靠层**。核心位置："过去可信, 当下清晰."

职责边界（会话定的分工，严格遵守）：
- **星图 (Astrolabe)** — 地图 + 元数据（结构化导航，非向量大库）
- **玄武 (Xuanwu)** — 数据存储（完整文档 + SQLite + Qdrant + BlobStore）
- **记忆系统** — 向量召回（零散经验、对话、笔记）

## 你（Agent）要怎么开始

**遇到任何"星图怎么做 X"的问题，第一步就是查本地地图。** 有两份：

### 1. 星图自述地图 — "这个系统能做什么"

```python
from xingtu import XingTuService
svc = XingTuService(); svc.initialize()
mm = svc.matrix_map

mm.overview()                         # 有哪些能力域
mm.enter_area("area-xingtu-search")   # 某域下的 organ
mm.get_organ("organ-xingtu-search")   # organ 详情 + operations
mm.get_operation("op-xingtu-hybrid-search")   # 单个操作的 1-3 个 docs
mm.find("trust")                      # 关键词找 op (支持 snake_case)
```

对应 MCP 工具前缀: `xingtu_map_*`。

### 2. Matrix 操作地图 — "Matrix 怎么用"

```python
mm.overview()                          # Matrix + 星图自述一起显示
# id 前缀 area-* 是 Matrix, area-xingtu-* 是本系统
mm.enter_area("area-discussion")
mm.get_room("room-discussion-room-wide")
mm.get_operation("op-create-discussion")
```

## 协作原则（2026-04-21 Trine 定）

**人给方向 AI 做决策。** 遇到多选别反问"A 还是 B"——直接选一个 + 理由 + 回退方案。
- 人的输入是"方向"（生产级 / 别重复造轮子 / 优先中文）
- AI 的输出是"决策"（KMeans / 阈值 / 命名）
- 不可逆动作（rm -rf / push 等）仍要确认

## 关键技术约定

- **VECTOR_DIM** 可通过 `XINGTU_VECTOR_DIM` env 调（默认 1536, BGE-M3 用 1024）
- **upsert** `add_documents` 传自定义 `document_ids` 时是 delete-then-add
- **Collection 幂等键** 是 `(name, tenant_id, collection_type)` 三元组
- **密钥永不入 yaml** — `config_loader` 自动阻断 `token/secret/password/api_key/auth` 字段

## 不要做

- 不要把原始文档全文入星图（那是玄武的活）
- 不要把大规模向量召回当星图的主路径（那是记忆系统）
- 不要直接读 docs/matrix-map/MATRIX_OPS_MAP.yaml（27KB+ 吞整块，用 mm.\* API 按需取）
- 不要新建重复概念（用 Collection/Document/Relation 就能表达的不要加新表）

## 常用调试

```bash
# 重建地图
rm -rf ~/.xingtu/data
python3 scripts/import_matrix_map.py
python3 scripts/import_xingtu_map.py

# 校验地图 yaml
cd docs/matrix-map && make validate
cd docs/xingtu-map && make validate    # 如有

# 看星图里有多少数据
python3 -c "from xingtu import XingTuService; s=XingTuService(); s.initialize(); print(s.get_stats())"
```

## 提交流程

- 一次一个 PR（不要把多个特性堆一起）
- 子 agent review 重点问题后再合并
- README 相关改动必须和代码改动同 PR（文档和代码不能漂移）
