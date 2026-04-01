# 星图 (XingTu) 事件驱动数据库设计 v2

> 版本: v0.2.0 | 新增: 事件表、决策日志、审核队列

## 1. 新增表概览

| 表名 | 归属 | 说明 |
|------|------|------|
| `events` | 影澜轩 | 事件总线持久化 |
| `ai_decisions` | 星空座 | AI 决策日志 |
| `review_queue` | 语界枢 | 待审核队列 |
| `xingji_executions` | 序律腺 | 行技执行记录 |
| `notifications` | 语界枢 | 通知记录 |
| `user_preferences` | 语界枢 | 用户偏好设置 |

## 2. 事件表

### 2.1 events（事件总线持久化）

```sql
CREATE TABLE events (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 事件信息
    event_type TEXT NOT NULL,           -- file.dropped, object.created, etc.
    source TEXT NOT NULL,               -- 来源组件
    correlation_id TEXT,                -- 关联 ID（追踪事件链）
    
    -- 事件数据
    payload JSON NOT NULL,
    
    -- 时间
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 处理状态
    processed INTEGER DEFAULT 0,        -- 是否已处理
    processed_at DATETIME,
    processor TEXT                      -- 处理者
);

-- 索引
CREATE INDEX idx_event_type ON events(event_type);
CREATE INDEX idx_event_timestamp ON events(timestamp);
CREATE INDEX idx_event_correlation ON events(correlation_id);
CREATE INDEX idx_event_processed ON events(processed, timestamp);
```

### 2.2 事件类型枚举

```yaml
event_types:
  # 文件事件
  - file.dropped
  - file.parsed
  - file.parse_failed
  
  # 对象事件
  - object.created
  - object.updated
  - object.properties_ready
  - object.ready
  - object.confirmed
  - object.archived
  
  # AI 决策事件
  - ai.decision_made
  - ai.decision_applied
  - ai.decision_rejected
  - ai.decision_rolled_back
  
  # 审核事件
  - review.created
  - review.approved
  - review.rejected
  - review.modified
  - review.expired
  
  # 行技事件
  - xingji.started
  - xingji.completed
  - xingji.failed
  
  # 通知事件
  - notify.sent
  - notify.read
```

## 3. AI 决策日志

### 3.1 ai_decisions（AI 决策记录）

```sql
CREATE TABLE ai_decisions (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 来源
    agent_type TEXT NOT NULL,           -- semantic_inference, relation_discovery
    xingji_execution_id TEXT,           -- 关联的行技执行 ID
    
    -- 目标
    object_id TEXT NOT NULL REFERENCES meta_objects(id),
    property_id TEXT REFERENCES meta_properties(id),
    relation_id TEXT REFERENCES meta_relations(id),
    
    -- 决策内容
    action_type TEXT NOT NULL,          -- rename, set_type, set_description, create_relation
    proposed_value JSON NOT NULL,       -- 建议的值
    previous_value JSON,                -- 之前的值（用于回滚）
    
    -- AI 分析
    confidence REAL NOT NULL,           -- 0.0 - 1.0
    reasoning TEXT,                     -- AI 推理过程
    
    -- 状态
    status TEXT DEFAULT 'pending',      -- pending, applied, rejected, rolled_back
    was_auto_applied INTEGER DEFAULT 0, -- 是否自动应用
    
    -- 时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    applied_at DATETIME,
    
    -- 审核
    review_id TEXT,                     -- 关联的审核项
    reviewed_by TEXT,
    reviewed_at DATETIME
);

-- 索引
CREATE INDEX idx_decision_object ON ai_decisions(object_id);
CREATE INDEX idx_decision_status ON ai_decisions(status);
CREATE INDEX idx_decision_agent ON ai_decisions(agent_type);
CREATE INDEX idx_decision_confidence ON ai_decisions(confidence);
```

### 3.2 action_type 枚举

```yaml
action_types:
  # 属性级操作
  - rename                  # 重命名字段
  - set_semantic_type       # 设置语义类型
  - set_description         # 设置描述
  - set_unit               # 设置单位
  - set_format             # 设置显示格式
  - set_visual_preference  # 设置可视化偏好
  
  # 关系级操作
  - create_relation        # 创建关系
  - update_relation        # 更新关系
  - remove_relation        # 移除关系
  
  # 对象级操作
  - rename_object          # 重命名对象
  - set_object_description # 设置对象描述
  - add_tag               # 添加标签
```

## 4. 审核队列

### 4.1 review_queue（待审核队列）

```sql
CREATE TABLE review_queue (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 关联决策
    decision_id TEXT NOT NULL REFERENCES ai_decisions(id),
    
    -- 快照（避免关联查询）
    object_id TEXT NOT NULL,
    object_name TEXT NOT NULL,
    property_id TEXT,
    property_name TEXT,
    
    -- 决策摘要
    agent_type TEXT NOT NULL,
    action_type TEXT NOT NULL,
    proposed_value JSON NOT NULL,
    current_value JSON,
    confidence REAL NOT NULL,
    reasoning TEXT,
    
    -- 上下文（帮助审核）
    sample_values JSON,                 -- 样本值
    related_context TEXT,               -- 相关上下文
    
    -- 状态
    status TEXT DEFAULT 'pending',      -- pending, approved, rejected, modified, expired
    priority INTEGER DEFAULT 0,         -- 优先级（高置信度优先）
    
    -- 审核
    reviewed_by TEXT,
    reviewed_at DATETIME,
    review_comment TEXT,
    modified_value JSON,                -- 如果是 modified 状态
    
    -- 时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,                -- 自动过期时间
    
    -- 批次
    batch_id TEXT                       -- 批量审核用
);

-- 索引
CREATE INDEX idx_review_status ON review_queue(status);
CREATE INDEX idx_review_object ON review_queue(object_id);
CREATE INDEX idx_review_created ON review_queue(created_at);
CREATE INDEX idx_review_priority ON review_queue(priority DESC, created_at);
```

### 4.2 review_status 枚举

```yaml
review_status:
  - pending    # 待审核
  - approved   # 已采纳
  - rejected   # 已拒绝
  - modified   # 修改后采纳
  - expired    # 已过期（未审核自动过期）
```

## 5. 行技执行记录

### 5.1 xingji_executions（行技执行记录）

```sql
CREATE TABLE xingji_executions (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 行技信息
    xingji_id TEXT NOT NULL,            -- xingji.auto_import, etc.
    xingji_version TEXT,
    
    -- 触发信息
    trigger_event_id TEXT REFERENCES events(id),
    trigger_event_type TEXT,
    correlation_id TEXT,                -- 事件链 ID
    
    -- 上下文
    input_params JSON,
    target_object_id TEXT,
    
    -- 执行状态
    status TEXT DEFAULT 'pending',      -- pending, running, completed, failed, cancelled
    current_cell TEXT,                  -- 当前执行的胞式
    progress REAL DEFAULT 0,            -- 0.0 - 1.0
    
    -- 结果
    output JSON,
    error_message TEXT,
    
    -- 统计
    cells_total INTEGER,
    cells_completed INTEGER,
    decisions_made INTEGER,
    decisions_applied INTEGER,
    reviews_queued INTEGER,
    
    -- 时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    duration_ms INTEGER
);

-- 索引
CREATE INDEX idx_exec_xingji ON xingji_executions(xingji_id);
CREATE INDEX idx_exec_status ON xingji_executions(status);
CREATE INDEX idx_exec_correlation ON xingji_executions(correlation_id);
CREATE INDEX idx_exec_created ON xingji_executions(created_at);
```

## 6. 通知记录

### 6.1 notifications（通知记录）

```sql
CREATE TABLE notifications (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 通知内容
    notification_type TEXT NOT NULL,    -- import_complete, review_needed
    title TEXT NOT NULL,
    body TEXT,
    subtitle TEXT,
    
    -- 关联
    object_id TEXT,
    action_type TEXT,                   -- open_object, open_review_queue
    action_payload JSON,
    
    -- 状态
    is_read INTEGER DEFAULT 0,
    is_dismissed INTEGER DEFAULT 0,
    
    -- 渠道
    sent_in_app INTEGER DEFAULT 1,
    sent_system INTEGER DEFAULT 0,
    
    -- 时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME
);

-- 索引
CREATE INDEX idx_notif_read ON notifications(is_read, created_at);
CREATE INDEX idx_notif_type ON notifications(notification_type);
```

## 7. 用户偏好设置

### 7.1 user_preferences（用户偏好）

```sql
CREATE TABLE user_preferences (
    -- 主键
    key TEXT PRIMARY KEY,
    
    -- 值
    value JSON NOT NULL,
    
    -- 时间
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 预设值
INSERT INTO user_preferences (key, value) VALUES
    -- AI 置信度阈值
    ('ai.auto_apply_threshold', '0.85'),
    ('ai.review_threshold', '0.50'),
    
    -- 通知偏好
    ('notify.in_app', 'true'),
    ('notify.system', 'true'),
    ('notify.badge', 'true'),
    
    -- 审核偏好
    ('review.auto_expire_hours', '72'),
    ('review.batch_size', '10'),
    
    -- 行技偏好
    ('xingji.auto_relation_discovery', 'true'),
    ('xingji.auto_quality_check', 'false');
```

## 8. 触发规则表

### 8.1 trigger_rules（触发规则配置）

```sql
CREATE TABLE trigger_rules (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 规则信息
    name TEXT NOT NULL,
    description TEXT,
    
    -- 触发条件
    event_type TEXT NOT NULL,
    condition_expr TEXT,                -- JSON 表达式
    
    -- 动作
    action_type TEXT NOT NULL,          -- start_xingji, add_to_review, notify
    action_params JSON,
    
    -- 执行配置
    priority TEXT DEFAULT 'medium',     -- high, medium, low
    delay_ms INTEGER DEFAULT 0,
    batch_window_ms INTEGER,
    
    -- 状态
    enabled INTEGER DEFAULT 1,
    
    -- 时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);

-- 预置规则
INSERT INTO trigger_rules (id, name, event_type, condition_expr, action_type, action_params, priority) VALUES
    ('rule_auto_import', '文件自动导入', 'file.dropped', 
     '{"op": "in", "field": "payload.file_type", "values": ["csv", "xlsx", "json"]}',
     'start_xingji', '{"xingji_id": "xingji.auto_import"}', 'high'),
     
    ('rule_semantic_inference', '自动语义推断', 'object.created',
     '{"op": "eq", "field": "payload.status", "value": "draft"}',
     'start_xingji', '{"xingji_id": "xingji.semantic_inference"}', 'high'),
     
    ('rule_relation_discovery', '自动关系发现', 'object.properties_ready',
     '{"op": "gt", "field": "object_count", "value": 1}',
     'start_xingji', '{"xingji_id": "xingji.relation_discovery"}', 'medium');
```

## 9. 完整初始化脚本

```sql
-- ============================================
-- 星图 v0.2.0 事件驱动数据库初始化
-- ============================================

-- 包含 v0.1.0 的所有表
-- (meta_objects, meta_properties, meta_relations, metric_defs, meta_events)
-- 见 SCHEMA.md

-- ============================================
-- 新增: 事件总线表
-- ============================================

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    correlation_id TEXT,
    payload JSON NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0,
    processed_at DATETIME,
    processor TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_event_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_event_correlation ON events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_event_processed ON events(processed, timestamp);

-- ============================================
-- 新增: AI 决策日志表
-- ============================================

CREATE TABLE IF NOT EXISTS ai_decisions (
    id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL,
    xingji_execution_id TEXT,
    object_id TEXT NOT NULL,
    property_id TEXT,
    relation_id TEXT,
    action_type TEXT NOT NULL,
    proposed_value JSON NOT NULL,
    previous_value JSON,
    confidence REAL NOT NULL,
    reasoning TEXT,
    status TEXT DEFAULT 'pending',
    was_auto_applied INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    applied_at DATETIME,
    review_id TEXT,
    reviewed_by TEXT,
    reviewed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_decision_object ON ai_decisions(object_id);
CREATE INDEX IF NOT EXISTS idx_decision_status ON ai_decisions(status);
CREATE INDEX IF NOT EXISTS idx_decision_agent ON ai_decisions(agent_type);
CREATE INDEX IF NOT EXISTS idx_decision_confidence ON ai_decisions(confidence);

-- ============================================
-- 新增: 审核队列表
-- ============================================

CREATE TABLE IF NOT EXISTS review_queue (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_name TEXT NOT NULL,
    property_id TEXT,
    property_name TEXT,
    agent_type TEXT NOT NULL,
    action_type TEXT NOT NULL,
    proposed_value JSON NOT NULL,
    current_value JSON,
    confidence REAL NOT NULL,
    reasoning TEXT,
    sample_values JSON,
    related_context TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    reviewed_by TEXT,
    reviewed_at DATETIME,
    review_comment TEXT,
    modified_value JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    batch_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_review_object ON review_queue(object_id);
CREATE INDEX IF NOT EXISTS idx_review_created ON review_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_review_priority ON review_queue(priority DESC, created_at);

-- ============================================
-- 新增: 行技执行记录表
-- ============================================

CREATE TABLE IF NOT EXISTS xingji_executions (
    id TEXT PRIMARY KEY,
    xingji_id TEXT NOT NULL,
    xingji_version TEXT,
    trigger_event_id TEXT,
    trigger_event_type TEXT,
    correlation_id TEXT,
    input_params JSON,
    target_object_id TEXT,
    status TEXT DEFAULT 'pending',
    current_cell TEXT,
    progress REAL DEFAULT 0,
    output JSON,
    error_message TEXT,
    cells_total INTEGER,
    cells_completed INTEGER,
    decisions_made INTEGER,
    decisions_applied INTEGER,
    reviews_queued INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_exec_xingji ON xingji_executions(xingji_id);
CREATE INDEX IF NOT EXISTS idx_exec_status ON xingji_executions(status);
CREATE INDEX IF NOT EXISTS idx_exec_correlation ON xingji_executions(correlation_id);

-- ============================================
-- 新增: 通知记录表
-- ============================================

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    subtitle TEXT,
    object_id TEXT,
    action_type TEXT,
    action_payload JSON,
    is_read INTEGER DEFAULT 0,
    is_dismissed INTEGER DEFAULT 0,
    sent_in_app INTEGER DEFAULT 1,
    sent_system INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(is_read, created_at);
CREATE INDEX IF NOT EXISTS idx_notif_type ON notifications(notification_type);

-- ============================================
-- 新增: 用户偏好设置表
-- ============================================

CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 新增: 触发规则表
-- ============================================

CREATE TABLE IF NOT EXISTS trigger_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    event_type TEXT NOT NULL,
    condition_expr TEXT,
    action_type TEXT NOT NULL,
    action_params JSON,
    priority TEXT DEFAULT 'medium',
    delay_ms INTEGER DEFAULT 0,
    batch_window_ms INTEGER,
    enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);
```

## 10. 迁移脚本

### v0.1.0 → v0.2.0

```sql
-- migrations/002_event_driven.sql

-- 事件表
CREATE TABLE IF NOT EXISTS events (...);

-- AI 决策表
CREATE TABLE IF NOT EXISTS ai_decisions (...);

-- 审核队列
CREATE TABLE IF NOT EXISTS review_queue (...);

-- 行技执行记录
CREATE TABLE IF NOT EXISTS xingji_executions (...);

-- 通知
CREATE TABLE IF NOT EXISTS notifications (...);

-- 用户偏好
CREATE TABLE IF NOT EXISTS user_preferences (...);

-- 触发规则
CREATE TABLE IF NOT EXISTS trigger_rules (...);

-- 更新版本
INSERT INTO schema_migrations (version) VALUES ('0.2.0');
```
