# Astrolabe 定位 — Python lib 优先, REST 是 Adapter

## What it is

**Astrolabe 是一个 Python 库**, 提供"元数据可靠层"能力 (Collection / Document / Relation / Event / Metadata pin / Trust scoring). 默认嵌入到调用方进程, 不需要独立部署。

LanceDB 本身就是 embedded 数据库 (跟 SQLite 同模型), Astrolabe 沿用这个形态。

## What it isn't

- **不是"通用基建对外服务"** — 当前用户=1 (项目 owner), 多租户/SaaS 投入产出比不成立
- **不是 Vector DB 替代品** — 大规模向量召回交给玄武 / Qdrant, 星图只做"元数据 + 结构化导航"
- **不是文档全文存储** — 原始文档全文在玄武 / 对象存储, 星图只持有"指向 + 元数据"

## 4 种使用路径

| 路径 | 谁用 | 怎么用 |
|------|------|--------|
| **1. Python lib (默认 / 首选)** | FYD, 任何同进程 Python 项目 | `from xingtu import XingTuService` 同进程, 零网络 |
| **2. Matrix REST Adapter** | Matrix (Go), 跨语言/跨进程客户端 | `xingtu_api` FastAPI, area_key Bearer 鉴权, fly.io 部署 |
| **3. Claude Desktop MCP** | Claude Desktop / Claude Code | `xingtu_mcp.server` stdio |
| **4. CLI** | 本地 dev / 数据导入脚本 | `xingtu` 命令 |

## lib vs REST 决策树

```
你的客户端是 Python 进程吗?
├── 是 → 用 lib (路径 1). 不要为了"好看"绕一圈走 REST.
└── 否 → 是跨语言或跨网络吗?
    ├── 是 (Go / TypeScript / 浏览器) → 用 REST (路径 2)
    └── 否 → 重新审视, 多半是路径 1 的伪需求
```

**铁律**: 同语言、同进程能解决的事, 不要走网络。

## fly.io 部署的真实角色

`https://astrolabe.fly.dev` 当前部署的形态是"REST Adapter (路径 2) 的实例", **不是**"Astrolabe 通用对外服务"。它真正的客户只有: Matrix Go (跨语言)。

未来如果有真实付费第三方客户, 才考虑把这台升级成"通用基建服务"。当前不是。

## 指标边界 (谁度量谁)

[PR #9](https://github.com/trine777/astrolabe/pull/9) 引入的指标体系遵循同一边界:

| 谁的指标 | 项数 | 暴露在哪 |
|---------|-----|---------|
| **Astrolabe (基建)** | 9: 8 L1 容量 + api_error_rate | `astrolabe.fly.dev/api/v1/observability/dashboard` |
| **FYD (产品)** | 8: W12/W4/采纳/付费/议会质量/成功率/报告/搜索 | FYD 自己 dashboard (W2+ 起 FastAPI), 走 lib 调 `xingtu.observability` |

`xingtu.observability` 模块是 **lib 工具**, 17 项计算函数全保留, FYD 直接 import 用. Astrolabe 自己的 REST dashboard 只展示基建那 9 项 — 不混"FYD 用户付费率"这种业务指标进去。

`/api/v1/observability/metrics` JSON 端点仍返回 17 项原始数据 (lib `all_metrics()` 不变), 给 FYD 后端聚合或外部脚本读取。只是 HTML dashboard 与 health 阈值汇总判 9 项。

## 与 FYD 的关系

FYD (12周 AI 议会陪跑产品) 是 Astrolabe 的首位真实使用者. 默认走路径 1:

```python
# FYD 启动时 (同一 fly app 或本地)
from xingtu import XingTuService
self.xingtu = XingTuService(db_path="/data/xingtu")
self.xingtu.initialize()
# 议会归档、决议存储、检索都同进程调用
```

**FYD 不依赖 `astrolabe.fly.dev`**, 自己 fly app 内嵌 lib + 自己的 LanceDB volume。

## Stoa α 角色

Stoa α 是早期为"验证 REST 契约"设的虚构外部客户。其使命随 R2 BGE-M3 cutover (2026-05-05) 完成而结束。之后 fly.io 那台只服务 Matrix。

## 相关文档

- `README.md` — Quick Start 4 paths 入口
- `docs/PRODUCTIZATION.md` — Matrix REST Adapter 的服务化设计 (Phase 0)
- `docs/DOCKER_DEPLOYMENT.md` — REST Adapter 部署细节 (路径 2 用)
- `docs/MCP_SERVER.md` — MCP 模式 (路径 3 用)
