# Matrix 操作地图 — 维护手册

**定位**：Agent 加载此地图即知道 Matrix 怎么用。
不是文档仓库，是可机读的**操作指南**。

## 第一次跑（60 秒上手）

```bash
# 1. 拿到 Matrix token（从管理员）
export MATRIX_PROD_TOKEN='xxx'                # 放 ~/.zshrc 持久化

# 2. 从 Matrix API 拉 live 数据
make sync                                      # 默认 ENV=prod

# 3. 校验（初次会因 stub 占位符报错，正常）
make validate

# 4. 填完 areas/ 和 rooms/ 内容后，产出地图
make build                                     # 生成 MATRIX_OPS_MAP.yaml
```

## 结构

```
docs/matrix-map/
├── config.yaml                   # 多环境配置（URL/token_env/caller_id）
├── config.local.yaml.example     # 本地覆盖模板（复制后改）
├── config.local.yaml             # 本地覆盖（gitignore）
├── schema.yaml                   # 节点 schema 定义
├── areas/                        # L1 Area（手工组织）
├── rooms/                        # L2 Room（sync.py 生成 stub，gitignore）
├── live/                         # ⚠️ 自动生成，勿手改
│   ├── rooms.json                # Matrix API 当前 room 清单（去重）
│   └── last_sync.json            # 同步元数据（env / 时间 / sha256）
├── scripts/
│   ├── config_loader.py          # 配置加载（含 token 关键字阻断）
│   ├── sync.py                   # 从 Matrix API 拉 live
│   ├── validate.py               # 校验 yaml 合规
│   └── build.py                  # 合并产出 MATRIX_OPS_MAP.yaml
├── Makefile
└── MATRIX_OPS_MAP.yaml           # ⚠️ 自动生成，勿手改（gitignore）
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
3. **每个节点必须有 `verified_at`**（默认 14 天过期需刷新；空串/TODO 占位不行）
4. **build 时 live 数据不能超过 `live_stale_days` 天**（默认 7）
5. **orphan room 默认阻断 build**（parent 未匹配的 room 不允许混入地图）
6. **密钥永不入仓**（config_loader 会阻断 yaml 中含 `token/secret/password` 字段）

## 给 Agent 的 3 条铁律

1. **改之前先拉**：`make sync` 拉最新 live
2. **改之后校验**：`make validate` 失败不允许 commit
3. **不绕过校验**：CI 阻断 + PR review

## 常用命令

```bash
# 日常
make sync              # env=prod（默认，与 commit 的 live 对齐）
make sync ENV=test     # 切测试环境
make validate          # 校验
make validate-strict   # warning 也当 error
make build             # 产出 MATRIX_OPS_MAP.yaml
make check             # sync + validate 一键
make all               # sync + validate + build
make clean             # 清 live 和生成物

# 临时覆盖（Makefile 透传）
make sync URL=http://localhost:8080
make sync CALLER=my-debug-caller
make sync TOKEN_FILE=~/.matrix-token     # 推荐：从文件读 token
```

## Token 传递方式（安全级别从高到低）

1. **环境变量**（推荐）：`export MATRIX_PROD_TOKEN=xxx` 放 shell 配置
2. **文件 + `--token-file`**：`echo $TOKEN > ~/.matrix-token && chmod 600 ~/.matrix-token`
3. **`--token` CLI 参数**（不推荐）：会进 shell history 和 CI 日志，脚本会打 WARNING

**永远不允许**：把 token 写进任何 yaml。`config_loader` 发现 yaml 里有 `token/secret/password/api_key/auth` 字段会直接退出。

## 配置优先级

高 → 低：
1. CLI 参数 (`--url`, `--token-file`, `--env`)
2. 环境变量 (`MATRIX_URL`, `MATRIX_TOKEN`, `MATRIX_ENV`, `MATRIX_TIMEOUT`)
3. `config.local.yaml`（gitignored，本地专属）
4. `config.yaml`（仓库基线）
5. 脚本兜底值

**注意**：token 本身只能走 env var 或 `--token-file`，yaml 里的 `token_env` 字段（环境变量名）可被 local 覆盖。

## 新增 / 修改 节点的流程

### 加新 Area (L1)

1. 在 `areas/` 下新建 `<slug>.yaml`
2. 必填：`id / title / kind: area / verified_at`
3. `make validate`

### 加新 Room (L2)

不手动建。Matrix 注册新 room 后：
```bash
make sync
# sync.py 会自动在 rooms/ 下生成 stub
# 然后编辑 stub，填 title / parent / operations / docs / verified_at
make validate
```

### 加新 Operation (L3)

在对应 `rooms/<key>.yaml` 里 `operations:` 数组追加：
```yaml
operations:
  - id: op-start-discussion
    kind: operation
    title: 起一个讨论
    parent: room-discussion-room-wide
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
| prod | https://matrix-os.fly.dev      | MATRIX_PROD_TOKEN（**默认**） |
| local | http://127.0.0.1:8080         | MATRIX_LOCAL_TOKEN |

改 URL 只改 `config.yaml`，不改脚本。

## source 字段说明

每个节点有 `source` 字段，标记数据来源：

| source | 含义 | 谁写 |
|--------|------|------|
| `human` | 人工整理的运维知识 | 维护者 |
| `api` | 从 Matrix API 同步的字段 | sync.py |
| `memory` | 从记忆系统导出的决议/经验 | 维护者 |
| `discussion` | 从 Matrix 讨论 room 决议导出 | 维护者 |

## 校验规则一览

| 级别 | 编码 | 说明 |
|------|------|------|
| error | E1 | id 全局唯一 |
| error | E2 | parent 必须存在 |
| error | E3 | kind ∈ {area, room, operation} |
| error | E4 | operation 节点 docs 数 1-3 |
| error | E5 | 必填字段齐全（空串/TODO 占位符一并算缺失） |
| error | E6 | room_key 必须在 live |
| error | E7 | doc type + title + content 齐全 |
| warn | W1 | verified_at 过期 |
| warn | W2 | live 有 room / rooms/ 下无 yaml |
| warn | W3 | curl 格式疑似不对 |
| warn | W4 | area 无 room 子 / room 无 operation 子 |
| warn | W5 | live 数据超过 live_stale_days 未刷新 |

`make validate-strict` 下 warning 当 error。

## Build 额外保护

- **E1**: live 数据超 `validate.live_stale_days` 天 → build 失败（`--skip-live-check` 可绕）
- **E2**: 发现 orphan room（parent 未匹配）→ build 失败（`build.fail_on_orphan=false` 可关）
- **D1**: live 出现同 `room_key` 重复时，按 `version` 取最高（sync 和 build 两处一致）
- **C3**: sync 时若 `last_sync.env` 与当前 env 不一致 → 警告（防数据混）

## 故障排查

**Q: `make validate` 报 E5 说 title 是占位符？**
→ sync.py 生成的 stub 把 title/parent/verified_at 留空，必须手工填才能过校验。这是故意设计，不是 bug。

**Q: `make build` 说 live 已 N 天未刷新？**
→ 先 `make sync`。或者调大 `config.yaml` 的 `validate.live_stale_days`。

**Q: `make build` 报 orphan room？**
→ 某个 room.yaml 的 `parent` 指向了不存在的 area id。去 `areas/` 下加对应 area，或改 room 的 parent。

**Q: `make sync` 说 live 重复 room_key？**
→ Matrix API 返回了同 key 的多个 version（如 v1 和 v2）。sync.py 会自动保留 version 最高的一条，记录在 `last_sync.json.dedup_conflicts`。

**Q: 切换环境后看到奇怪的 stub？**
→ sync.py 检测 `last_sync.env != current_env` 会警告。按提示 `make clean` 或切回原 env。
