# Matrix 操作地图 — 维护手册

**定位**：Agent 加载此地图即知道 Matrix 怎么用。
不是文档仓库，是可机读的**操作指南**。

## 结构

```
docs/matrix-map/
├── config.yaml              # 环境配置（URL/token_env/caller_id）
├── config.local.yaml        # 本地覆盖（gitignore）
├── schema.yaml              # 节点 schema 定义
├── areas/                   # L1 Area（手工组织）
├── rooms/                   # L2 Room（对应 Matrix room_key）
├── live/                    # ⚠️ 自动生成，勿手改
│   ├── rooms.json           # Matrix API 当前 room 清单
│   └── last_sync.json       # 同步元数据
├── scripts/
│   ├── config_loader.py     # 配置加载
│   ├── sync.py              # 从 Matrix API 拉 live
│   ├── validate.py          # 校验 yaml 合规
│   └── build.py             # 合并产出 MATRIX_OPS_MAP.yaml
├── Makefile
└── MATRIX_OPS_MAP.yaml      # ⚠️ 自动生成，勿手改
```

## 三层层级

```
Area (L1)       例: 讨论决议 / 开发迭代 / 治理运维
  └─ Room (L2)  对应 Matrix 的 room_key (discussion-room-wide / matrix_iteration ...)
      └─ Operation (L3)  例: 起一个讨论 / 查状态
          └─ docs  1-3 个 (curl/rule/checklist/diagram/payload)
```

## 核心硬约束

1. **operation 节点必须挂 1-3 个 docs**（下限防空壳，上限防颗粒度太粗）
2. **room 的 `room_key` 必须在 `live/rooms.json` 中存在**（防过期）
3. **每个节点必须有 `verified_at`**（默认 14 天过期需刷新）
4. **密钥永不入仓**（只从环境变量读）

## 给 Agent 的 3 条铁律

1. **改之前先拉**：`make sync ENV=prod` 拉最新 live
2. **改之后校验**：`make validate` 失败不允许 commit
3. **不绕过校验**：CI 阻断 + PR review

## 常用命令

```bash
# 首次使用 - 设置 token
export MATRIX_TEST_TOKEN=xxx       # 从 Matrix 管理员拿
export MATRIX_PROD_TOKEN=yyy

# 日常
make sync              # env=test
make sync ENV=prod     # 切环境
make validate          # 校验
make validate-strict   # warning 也当 error
make build             # 产出 MATRIX_OPS_MAP.yaml
make check             # sync + validate 一键

# 调试（覆盖 URL/token）
python3 scripts/sync.py --url http://localhost:8080 --token xxx
```

## 配置优先级

高 → 低：
1. CLI 参数 (`--url`, `--token`, `--env`)
2. 环境变量 (`MATRIX_URL`, `MATRIX_TOKEN`, `MATRIX_ENV`)
3. `config.local.yaml`
4. `config.yaml`
5. 脚本兜底值

## 新增 / 修改 节点的流程

### 加新 Area (L1)

1. 在 `areas/` 下新建 `<slug>.yaml`
2. 必填: `id / title / kind: area / verified_at`
3. `make validate`

### 加新 Room (L2)

不手动建。Matrix 注册新 room 后：
```bash
make sync
# sync.py 会自动在 rooms/ 下生成 stub
# 然后编辑 stub，填 parent / operations / docs
make validate
```

### 加新 Operation (L3)

在对应 `rooms/<key>.yaml` 里 `operations:` 数组追加：
```yaml
operations:
  - id: op-start-discussion
    title: 起一个讨论
    kind: operation
    verified_at: 2026-04-21
    verified_by: claude
    docs:
      - type: curl
        title: 7步脚本
        language: bash
        content: |
          # curl -X POST ...
```

## 环境差异

| 环境 | URL | Token 环境变量 |
|-----|-----|---------------|
| test | https://matrix-os-test.fly.dev | MATRIX_TEST_TOKEN |
| prod | https://matrix-os.fly.dev      | MATRIX_PROD_TOKEN |
| local | http://127.0.0.1:8080         | MATRIX_LOCAL_TOKEN |

改 URL 只改 `config.yaml`，不改脚本。

## 校验规则一览

| 级别 | 编码 | 说明 |
|------|------|------|
| error | E1 | id 全局唯一 |
| error | E2 | parent 必须存在 |
| error | E3 | kind ∈ {area, room, operation} |
| error | E4 | operation 节点 docs 数 1-3 |
| error | E5 | 必填字段齐全 |
| error | E6 | room_key 必须在 live |
| error | E7 | doc type + title + content 齐全 |
| warn | W1 | verified_at 过期 |
| warn | W2 | live 有 room / rooms/ 下无 yaml |
| warn | W3 | curl 格式疑似不对 |

`make validate-strict` 下 warning 当 error。
