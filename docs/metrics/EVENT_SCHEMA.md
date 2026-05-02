# Metric Event Schema v0.1

> 14 个 event_type 覆盖 17 个指标 (4 价值 + 5 体验 + 8 容量).
> 所有事件复用现有 `events` 表 + 现有 `Event` 模型, 不新建 schema.

## 字段映射约定

`Event` 模型字段在指标场景下的用法:

| Event 字段 | 用法 |
|-----------|------|
| `event_type` | 命名空间: `fyd.*` / `api.request` / `internal.*` / `auth.attempt` |
| `target_type` | 统一填 `metric_event` |
| `target_id` | 自然键 (session_id / search_id / user_id, 见各事件) |
| `actor_type` | `user` / `ai` / `system` |
| `actor_id` | user_id (如适用) |
| `description` | 人类可读简述, 非必填 |
| `after_snapshot` | **JSON 字符串, 即 metadata payload** (核心载体) |
| `before_snapshot` | 不用 |

> **为什么用 `after_snapshot` 不加新字段?** Event 表已上线生产 (fly.io). 新增字段需要 LanceDB schema migration; 而 `after_snapshot` 已是 `Optional[str]` JSON, 语义可复用。代价: 字段名不直观, 用本文档约束。

## emit 调用模板

```python
import json
service.events.emit(
    event_type="fyd.session_started",
    target_type="metric_event",
    target_id=session_id,
    actor_type="user",
    actor_id=user_id,
    after_snapshot=json.dumps({
        "user_id": user_id,
        "profile_id": profile_id,
        # ...其他字段见下表
    }, ensure_ascii=False),
)
```

---

## L3 价值层事件 (5 个 event_type → 4 个指标)

### `fyd.session_started`
- **触发**: 用户启动一次议会 (call `run_discovery_council`)
- **target_id**: `session_id`
- **after_snapshot**:
  ```json
  {
    "user_id": "u_abc",
    "profile_id": "alex_ex_google",
    "topic_id": "topic_xyz",
    "week_number": 1
  }
  ```
- **驱动指标**: M-3.1 (分母), M-3.2 (分母), M-2.2 (分母)

### `fyd.session_completed`
- **触发**: 议会跑到 resolution 阶段并保存
- **target_id**: `session_id`
- **after_snapshot**:
  ```json
  {
    "user_id": "u_abc",
    "session_id": "sess_xyz",
    "week_number": 4,
    "resolution_id": "res_abc",
    "duration_seconds": 312
  }
  ```
- **驱动指标**: M-3.2 (分子, week_number≥4), M-2.2 (分子), M-2.3 (起点)

### `fyd.session_failed`
- **触发**: 议会未走完 (异常 / 超时 / 用户取消)
- **target_id**: `session_id`
- **after_snapshot**:
  ```json
  {
    "user_id": "u_abc",
    "session_id": "sess_xyz",
    "week_number": 4,
    "cancel_reason": "user_cancel | matrix_timeout | orchestrator_error",
    "stage": "framing | exploring | ..."
  }
  ```
- **驱动指标**: M-2.2 (`user_cancel` 从分母剔除)

### `fyd.session_scored`
- **触发**: 人工或 LLM-as-judge 给议会发言打分
- **target_id**: `session_id`
- **after_snapshot**:
  ```json
  {
    "session_id": "sess_xyz",
    "score": 4,
    "scorer": "trine | llm_judge",
    "dimensions": {
      "insight": 4,
      "actionable": 5,
      "coherence": 4
    },
    "comment": "可选评语"
  }
  ```
- **驱动指标**: M-2.1

### `fyd.report_generated`
- **触发**: PDF/MD 周报告生成完成
- **target_id**: `session_id`
- **after_snapshot**:
  ```json
  {
    "user_id": "u_abc",
    "session_id": "sess_xyz",
    "week_number": 12,
    "format": "pdf | markdown",
    "generation_ms": 4520,
    "report_path": "reports/u_abc/w12.pdf"
  }
  ```
- **驱动指标**: M-3.1 (分子, week_number=12), M-2.3 (终点)

### `fyd.subscription_paid`
- **触发**: Stripe webhook `invoice.paid` (扣转写)
- **target_id**: `user_id`
- **after_snapshot**:
  ```json
  {
    "user_id": "u_abc",
    "plan": "monthly_29 | trial",
    "amount_usd": 29,
    "stripe_event_id": "evt_xxx",
    "period_start": "2026-05-01T00:00:00Z",
    "period_end": "2026-06-01T00:00:00Z"
  }
  ```
- **驱动指标**: M-3.4 (分子, plan ≠ "trial")

### `fyd.subscription_canceled`
- **触发**: Stripe webhook `customer.subscription.deleted`
- **target_id**: `user_id`
- **after_snapshot**:
  ```json
  {
    "user_id": "u_abc",
    "stripe_event_id": "evt_xxx",
    "reason": "user_initiated | payment_failed | refund"
  }
  ```
- **驱动指标**: M-3.4 (与 paid 比时间, 后者赢则不算 paid_now)

> **M-3.3 决议采纳率不走事件** — 直接读 `documents` 表 `collection_id=fyd_resolutions` 文档的 `metadata_json.adoption_status` 字段. 用户在 FYD 前端勾选 "已执行" 时 PUT 文档更新.

---

## L2 体验层事件 (复用 L3 + 2 个新 event_type)

### `fyd.search_performed`
- **触发**: 用户在 FYD 前端发起搜索
- **target_id**: `search_id` (前端生成 UUID)
- **after_snapshot**:
  ```json
  {
    "user_id": "u_abc",
    "search_id": "srch_xyz",
    "query": "AI 议会怎么用",
    "result_count": 8,
    "took_ms": 145
  }
  ```
- **驱动指标**: M-2.5 (分母)

### `fyd.search_clicked`
- **触发**: 用户点击搜索结果某一条
- **target_id**: `search_id` (与上同, 配对用)
- **after_snapshot**:
  ```json
  {
    "user_id": "u_abc",
    "search_id": "srch_xyz",
    "rank": 1,
    "result_doc_id": "doc_abc"
  }
  ```
- **驱动指标**: M-2.5 (分子, rank ≤ 3 且 click - search ≤ 30s)

> **M-2.4 API 错误率** 用 `api.request` 事件 (见下).

---

## L1 容量层事件 (5 个 event_type → 8 个指标)

### `api.request`
- **触发**: 每次 HTTP 请求结束 (FastAPI middleware, W1 实施)
- **target_id**: `request_id` (middleware 生成 UUID)
- **after_snapshot**:
  ```json
  {
    "route": "/api/v1/search/hybrid",
    "method": "GET",
    "status": 200,
    "latency_ms": 234,
    "tenant_id": "stoa-alpha",
    "area_key_prefix": "stoa_WHe"
  }
  ```
- **驱动指标**: M-1.1 (read p95), M-1.2 (write p95), M-2.4 (5xx 占比)

### `internal.embed`
- **触发**: `XingkongzuoStore.embed_texts` 内置 timer
- **target_id**: `request_id` (调用方传入或生成)
- **after_snapshot**:
  ```json
  {
    "provider": "sentence-transformers",
    "model": "BAAI/bge-m3",
    "batch_size": 64,
    "input_tokens": 12450,
    "latency_ms": 820,
    "status": "ok | fail"
  }
  ```
- **驱动指标**: M-1.3

### `internal.lancedb_query`
- **触发**: `store.search_documents` / `query_documents` 内置 timer
- **target_id**: `request_id`
- **after_snapshot**:
  ```json
  {
    "table": "documents",
    "op": "vector | filter | hybrid",
    "result_count": 12,
    "latency_ms": 45
  }
  ```
- **驱动指标**: M-1.4

### `internal.disk_check`
- **触发**: 后台任务每 1h 一次 `os.statvfs('/data')`
- **target_id**: `null` (单例)
- **after_snapshot**:
  ```json
  {
    "path": "/data",
    "used_bytes": 12345678,
    "total_bytes": 3221225472,
    "fly_volume_id": "vol_xxx"
  }
  ```
- **驱动指标**: M-1.5

### `internal.embed_ping`
- **触发**: 后台任务每 5min 一次 ping embedding provider
- **target_id**: `null`
- **after_snapshot**:
  ```json
  {
    "provider": "sentence-transformers",
    "endpoint": "https://...",
    "status": "ok | fail | timeout",
    "latency_ms": 105
  }
  ```
- **驱动指标**: M-1.6

### `auth.attempt`
- **触发**: AuthMiddleware 每次校验 area_key
- **target_id**: `request_id`
- **after_snapshot**:
  ```json
  {
    "area_key_prefix": "stoa_WHe",
    "tenant_id": "stoa-alpha",
    "status": 200,
    "route": "/api/v1/search/hybrid",
    "ip_hash": "sha256_truncated"
  }
  ```
- **驱动指标**: M-1.7 (status ∈ {401, 403} / 总), M-1.8 (distinct prefix 30d, status=200)

> **安全约定**: 永不存完整 `area_key`. 只存前 8 字符 `area_key_prefix` (审计够用). IP 用 sha256 截断 (避免明文持留).

---

## 完整命名空间速查

| event_type | target_id | after_snapshot 关键字段 | 指标 |
|-----------|-----------|----------------------|------|
| `fyd.session_started` | session_id | user_id, week_number | M-3.1, M-3.2, M-2.2 |
| `fyd.session_completed` | session_id | user_id, week_number, resolution_id | M-3.2, M-2.2, M-2.3 |
| `fyd.session_failed` | session_id | cancel_reason, stage | M-2.2 |
| `fyd.session_scored` | session_id | score, dimensions | M-2.1 |
| `fyd.report_generated` | session_id | week_number, generation_ms | M-3.1, M-2.3 |
| `fyd.subscription_paid` | user_id | plan, amount_usd | M-3.4 |
| `fyd.subscription_canceled` | user_id | reason | M-3.4 |
| `fyd.search_performed` | search_id | query, result_count | M-2.5 |
| `fyd.search_clicked` | search_id | rank, result_doc_id | M-2.5 |
| `api.request` | request_id | route, status, latency_ms | M-1.1, M-1.2, M-2.4 |
| `internal.embed` | request_id | provider, latency_ms | M-1.3 |
| `internal.lancedb_query` | request_id | op, latency_ms | M-1.4 |
| `internal.disk_check` | — | used/total_bytes | M-1.5 |
| `internal.embed_ping` | — | provider, status | M-1.6 |
| `auth.attempt` | request_id | status, area_key_prefix | M-1.7, M-1.8 |

**14 event_type 覆盖 17 指标** (M-3.3 走 documents 表). 零冗余, 零缺口.

---

## 实施时序

| 周 | 接 event_type | 谁写 |
|----|--------------|------|
| **W0** | `fyd.session_*`, `fyd.report_generated`, `fyd.session_scored` | FYD orchestrator + Trine 人评 |
| W1 | `api.request`, `auth.attempt` | Astrolabe FastAPI middleware |
| W2 | `fyd.search_*`, `fyd.subscription_*` | FYD 前端埋点 + Stripe webhook |
| W3 | `internal.embed`, `internal.lancedb_query` | XingkongzuoStore 内置 timer |
| W4 | `internal.disk_check`, `internal.embed_ping` | 后台 cron 任务 |

## 设计原则回顾

1. **零新表** — 复用 `events`, 命名空间隔离
2. **零必填字段添加** — `after_snapshot` 已是 Optional, 兼容旧数据
3. **target_id 选自然键** — 不是 random UUID, 是 session_id/search_id/user_id, 便于配对查询
4. **PII 最小化** — area_key 只存 prefix, IP hash, 用户 query 文本不长期存储 (W2 加 retention 策略)
