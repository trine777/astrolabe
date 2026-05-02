# `POST /api/v1/collections/{id}/reembed` — 异步全量重嵌

> **状态**: spec v0.1 (2026-04-28), 实现 ETA 2026-05-04
> **维护态**: Stoa α 退役 (R2 BGE-M3 cutover 2026-05-05 后), 此 REST 端点进入维护态。新接入者首选 lib 路径: `XingTuService.reembed_collection()` (W2 暴露). REST 仅给 Matrix (Go) 等跨语言客户端。
> **触发方**: Matrix / 跨语言客户端
> **关联**: R2 BGE-M3 cutover (5/5 上线广播 7 天前)
> **协议**: 提交即返 task_id, 轮询拿状态, 失败可重试, 同 idempotency_key 幂等

---

## Endpoint signature

### 提交

```
POST /api/v1/collections/{collection_id}/reembed
Authorization: Bearer <area_key>
Content-Type: application/json

{
  "embedding": {
    "provider": "sentence-transformers",   # 必填: 目标 provider
    "model":    "BAAI/bge-m3",              # 必填: 目标 model
    "dim":      1024                        # 必填: 必与服务端默认一致, 否则 422
  },
  "idempotency_key": "stoa-alpha-reembed-2026-05-05",  # 必填: 24h 内同 key 同 body 返同 task_id
  "options": {                              # 可选
    "force": false,                         # true=覆盖已 pin 的目标 model (危险)
    "batch_size": 64,                       # 默认 64, 1-256
    "include_archived": false,              # 默认仅 active doc
    "dry_run": false                        # true=只返预估时长, 不真跑
  }
}
```

### 返回 (HTTP 202 Accepted)

```json
{
  "task_id": "task-reembed-<uuid>",
  "collection_id": "<id>",
  "status": "queued",
  "queued_at": "2026-05-05T08:00:00Z",
  "estimated_completion_at": "2026-05-05T08:42:00Z",
  "estimated_documents": 4830,
  "estimated_cost_compute_seconds": 2520,
  "polling_url": "/api/v1/tasks/task-reembed-<uuid>",
  "polling_interval_hint_sec": 30
}
```

### 错误码

| HTTP | code | 含义 |
|------|------|------|
| 401 | `unauthorized` | 缺/错 area_key |
| 403 | `tenant_mismatch` | key 锁的 tenant 与 collection.tenant_id 不符 |
| 404 | `collection_not_found` | id 不存在 |
| 409 | `another_reembed_in_progress` | 同一 collection 已有 task in_progress, 同 idempotency_key 返旧 task_id 不报 409 |
| 422 | `embedding_pin_conflict` | 当前 collection.metadata.embedding 与提交目标 model 不一致, 且 `options.force=false` |
| 422 | `dim_mismatch` | 提交 dim 与服务端默认 (`XINGTU_VECTOR_DIM`) 不符 |
| 422 | `validation_error` | 字段缺失/类型错 |
| 503 | `embedding_provider_unavailable` | 目标 provider 服务端没装/不可达 |

---

## Polling: `GET /api/v1/tasks/{task_id}`

```
GET /api/v1/tasks/task-reembed-<uuid>
Authorization: Bearer <area_key>
```

### Status 状态机

```
queued
  ↓
running        ←─┐ (heartbeat 每 30s)
  ├─ partial   ─┘  (一部分成功, 重试可继续从断点)
  ├─ completed
  ├─ failed
  └─ canceled  (用户/系统主动取消)
```

### 返回 (运行中)

```json
{
  "task_id": "task-reembed-<uuid>",
  "type": "reembed",
  "collection_id": "<id>",
  "status": "running",
  "progress": {
    "total_documents": 4830,
    "processed_documents": 1240,
    "failed_documents": 0,
    "current_batch": 20,
    "total_batches": 76
  },
  "embedding": {
    "provider": "sentence-transformers",
    "model": "BAAI/bge-m3",
    "dim": 1024
  },
  "queued_at": "2026-05-05T08:00:00Z",
  "started_at": "2026-05-05T08:01:12Z",
  "last_heartbeat_at": "2026-05-05T08:14:30Z",
  "estimated_completion_at": "2026-05-05T08:42:00Z",
  "errors": []
}
```

### 返回 (完成)

```json
{
  "task_id": "...",
  "status": "completed",
  "completed_at": "2026-05-05T08:41:18Z",
  "progress": {
    "total_documents": 4830,
    "processed_documents": 4830,
    "failed_documents": 0
  },
  "summary": {
    "duration_seconds": 2406,
    "throughput_docs_per_sec": 2.0,
    "collection_metadata_updated": true,
    "old_pin": {
      "provider": "none",
      "model": null,
      "dim": 1536,
      "pinned_at": null
    },
    "new_pin": {
      "provider": "sentence-transformers",
      "model": "BAAI/bge-m3",
      "dim": 1024,
      "pinned_at": "2026-05-05T08:41:18Z"
    }
  }
}
```

### 返回 (partial — 失败要 retry 用)

```json
{
  "task_id": "...",
  "status": "partial",
  "progress": {
    "total_documents": 4830,
    "processed_documents": 4810,
    "failed_documents": 20
  },
  "errors": [
    {
      "document_id": "doc-xxx",
      "batch_index": 73,
      "error_code": "embedding_provider_timeout",
      "error_message": "Gemma server timed out at batch 73 doc 12",
      "occurred_at": "2026-05-05T08:39:21Z"
    }
  ],
  "retry_url": "/api/v1/tasks/task-reembed-<uuid>/retry",
  "retry_strategy": "resume_from_failed",
  "summary": {
    "duration_seconds": 2380,
    "collection_metadata_updated": false,
    "note": "Pin 不更新直到 status=completed. 当前 collection 仍处于双 vector 状态 (4810 新 + 20 旧)"
  }
}
```

---

## Retry: `POST /api/v1/tasks/{task_id}/retry`

```
POST /api/v1/tasks/<id>/retry
Authorization: Bearer <area_key>

{
  "strategy": "resume_from_failed"   # resume_from_failed | from_scratch
}
```

返回新 sub-task_id 或同 task_id (取决于策略). 同 idempotency 协议.

---

## Cancel: `POST /api/v1/tasks/{task_id}/cancel`

```
POST /api/v1/tasks/<id>/cancel
Authorization: Bearer <area_key>
```

返回 `{ "status": "canceled", "canceled_at": "...", "partial_progress": {...} }`.

被 cancel 的 task: collection metadata 不更新, 已 reembed 的 doc 保留新 vector (dim 可能与 pinned 不一致, 处于 inconsistent state, 必须再次提交 reembed 才一致).

---

## stoa 集成示例 (Go)

```go
// 1. 提交
resp, err := client.Post("/api/v1/collections/"+colID+"/reembed", body)
taskID := resp.TaskID

// 2. 轮询
ticker := time.NewTicker(30 * time.Second)
for range ticker.C {
    status, _ := client.Get("/api/v1/tasks/" + taskID)
    metrics.Gauge("reembed.progress", status.Progress.ProcessedDocuments)
    
    switch status.Status {
    case "completed":
        log.Info("reembed done", "new_pin", status.Summary.NewPin)
        return nil
    case "partial":
        log.Warn("reembed partial", "failed", status.Progress.FailedDocuments)
        return retryReembed(taskID)  // POST /retry
    case "failed":
        return fmt.Errorf("reembed failed: %v", status.Errors)
    }
}
```

---

## 服务端实现注记 (供 Astrolabe 内部参考)

- task 入 LanceDB `reembed_tasks` 表 (新表)
- worker: 后台进程 / Matrix scheduler 触发 / cron
- 每 batch 写 LanceDB delete-then-add (upsert)
- pin 更新只在 status=completed 那一刻原子写
- partial 状态下 collection 处于 inconsistent: 新旧 vector 混存, 但 metadata.embedding pin 未更新, 客户端写入校验仍走旧 pin
- 重试用 `failed_document_ids` 列表精准恢复
