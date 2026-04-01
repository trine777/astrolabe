# 星图 (XingTu) 数据库设计

> 版本: v0.1.0 | 存储: SQLite | 归属: 星空座

## 1. 概述

星图使用 SQLite 作为本地存储，数据模型围绕**星空座世界模型**设计。

### 核心表

| 表名 | 归属器官 | 说明 |
|------|---------|------|
| `meta_objects` | 星空座 | 元数据对象（数据源/表） |
| `meta_properties` | 星空座 | 元数据属性（字段/列） |
| `meta_relations` | 星空座 | 对象间关系 |
| `metric_defs` | 星空座 | 业务指标定义 |
| `meta_events` | 影澜轩 | 变更事件流 |

## 2. ER 图

```
┌─────────────────┐       ┌─────────────────┐
│  meta_objects   │──1:N──│ meta_properties │
│  (数据对象)     │       │  (属性/列)       │
└────────┬────────┘       └────────┬────────┘
         │                         │
         │ 1:N                     │
         ▼                         │
┌─────────────────┐                │
│  meta_relations │◀───────────────┘
│  (对象关系)     │
└─────────────────┘
         │
         │ N:1
         ▼
┌─────────────────┐
│   meta_events   │
│  (变更事件)     │
└─────────────────┘

┌─────────────────┐
│   metric_defs   │──N:M──│ meta_objects │
│  (指标定义)     │
└─────────────────┘
```

## 3. 表结构定义

### 3.1 meta_objects（元数据对象）

存储数据源/表的元信息，是星空座世界模型的核心实体。

```sql
CREATE TABLE meta_objects (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 基本信息
    name TEXT NOT NULL,                    -- 业务名称（用户定义）
    original_name TEXT NOT NULL,           -- 原始名称（文件名/表名）
    object_type TEXT NOT NULL,             -- 对象类型
    description TEXT,                      -- 业务含义描述
    
    -- 来源信息
    file_path TEXT,                        -- 原始文件路径
    row_count INTEGER,                     -- 数据行数
    
    -- 状态
    status TEXT DEFAULT 'draft',           -- draft/confirmed/published/archived
    
    -- 标签
    tags JSON,                             -- ["标签1", "标签2"]
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    confirmed_at DATETIME,                 -- 用户确认时间
    confirmed_by TEXT                      -- 确认人
);

-- 索引
CREATE INDEX idx_object_status ON meta_objects(status);
CREATE INDEX idx_object_type ON meta_objects(object_type);
CREATE INDEX idx_object_name ON meta_objects(name);
```

**object_type 枚举值：**

| 值 | 说明 |
|---|------|
| `csvFile` | CSV 文件 |
| `table` | 数据库表 |
| `view` | 视图 |
| `derived` | 派生数据集 |
| `external` | 外部数据源 |

**status 枚举值：**

| 值 | 说明 |
|---|------|
| `draft` | 草稿（AI 推断，待确认） |
| `confirmed` | 已确认（用户校验） |
| `published` | 已发布（可供分析） |
| `archived` | 已归档 |

### 3.2 meta_properties（元数据属性）

存储字段/列的语义信息，是星空座知识的核心载体。

```sql
CREATE TABLE meta_properties (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 外键
    object_id TEXT NOT NULL REFERENCES meta_objects(id) ON DELETE CASCADE,
    
    -- === 原始信息（从数据解析） ===
    original_name TEXT NOT NULL,           -- 原始列名
    data_type TEXT NOT NULL,               -- 物理数据类型
    sample_values JSON,                    -- 样本值 ["v1", "v2", ...]
    null_count INTEGER DEFAULT 0,          -- 空值数量
    unique_count INTEGER DEFAULT 0,        -- 唯一值数量
    
    -- === 用户定义的语义层（星空座核心） ===
    display_name TEXT,                     -- 业务名称
    description TEXT,                      -- 业务含义
    semantic_type TEXT,                    -- 语义类型
    unit TEXT,                             -- 单位（元、%、人）
    format TEXT,                           -- 显示格式
    business_rules TEXT,                   -- 业务规则说明
    
    -- === 可视化偏好 ===
    visual_preference JSON,                -- {chartType, colorScheme, aggregation}
    
    -- === AI 推断信息 ===
    ai_inferred JSON                       -- {inferredSemanticType, confidence, reasoning, inferredAt}
);

-- 索引
CREATE INDEX idx_prop_object ON meta_properties(object_id);
CREATE INDEX idx_prop_semantic ON meta_properties(semantic_type);
```

**data_type 枚举值：**

| 值 | 说明 |
|---|------|
| `string` | 字符串 |
| `integer` | 整数 |
| `decimal` | 小数 |
| `boolean` | 布尔 |
| `date` | 日期 |
| `datetime` | 日期时间 |
| `json` | JSON |
| `unknown` | 未知 |

**semantic_type 枚举值：**

| 分类 | 值 | 说明 |
|------|---|------|
| 标识类 | `primaryKey` | 主键 |
| | `foreignKey` | 外键 |
| | `uniqueId` | 唯一标识 |
| 实体类 | `personName` | 人名 |
| | `orgName` | 组织名 |
| | `productName` | 产品名 |
| | `placeName` | 地点名 |
| 联系类 | `email` | 邮箱 |
| | `phone` | 电话 |
| | `address` | 地址 |
| | `url` | 网址 |
| 度量类 | `amount` | 金额 |
| | `quantity` | 数量 |
| | `percentage` | 百分比 |
| | `ratio` | 比率 |
| | `score` | 评分 |
| 时间类 | `timestamp` | 时间戳 |
| | `dateOnly` | 仅日期 |
| | `timeOnly` | 仅时间 |
| | `duration` | 时长 |
| 分类类 | `category` | 分类 |
| | `status` | 状态 |
| | `tag` | 标签 |
| | `code` | 代码 |
| 其他 | `freeText` | 自由文本 |
| | `unknown` | 未知 |

**visual_preference JSON 结构：**

```json
{
  "chartType": "bar|line|pie|scatter|table",
  "colorScheme": "wind|fire|water|earth",
  "aggregation": "sum|avg|count|min|max"
}
```

**ai_inferred JSON 结构：**

```json
{
  "inferredSemanticType": "amount",
  "confidence": 0.85,
  "reasoning": "列名包含'金额'，样本值都是数字且有小数",
  "inferredAt": "2026-01-28T10:00:00Z"
}
```

### 3.3 meta_relations（元数据关系）

存储对象之间的关系，构建星空座语义图谱。

```sql
CREATE TABLE meta_relations (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 源端
    source_object_id TEXT NOT NULL REFERENCES meta_objects(id),
    source_property_id TEXT NOT NULL REFERENCES meta_properties(id),
    
    -- 目标端
    target_object_id TEXT NOT NULL REFERENCES meta_objects(id),
    target_property_id TEXT NOT NULL REFERENCES meta_properties(id),
    
    -- 关系信息
    relation_type TEXT NOT NULL,           -- 关系类型
    relation_name TEXT,                    -- 关系名称（"属于"、"包含"）
    description TEXT,                      -- 关系说明
    
    -- 确认状态
    is_ai_inferred INTEGER DEFAULT 0,      -- 是否 AI 推断
    confidence REAL,                       -- AI 置信度 0-1
    is_confirmed INTEGER DEFAULT 0,        -- 用户是否确认
    confirmed_at DATETIME
);

-- 索引
CREATE INDEX idx_relation_source ON meta_relations(source_object_id);
CREATE INDEX idx_relation_target ON meta_relations(target_object_id);
CREATE INDEX idx_relation_type ON meta_relations(relation_type);
```

**relation_type 枚举值：**

| 值 | 说明 |
|---|------|
| `oneToOne` | 1:1 关系 |
| `oneToMany` | 1:N 关系 |
| `manyToOne` | N:1 关系 |
| `manyToMany` | M:N 关系 |

### 3.4 metric_defs（指标定义）

存储业务指标定义，是星空座的衍生知识。

```sql
CREATE TABLE metric_defs (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 基本信息
    name TEXT NOT NULL UNIQUE,             -- 指标代码名
    display_name TEXT NOT NULL,            -- 显示名称
    description TEXT,                      -- 业务含义
    
    -- 计算逻辑
    formula TEXT NOT NULL,                 -- SQL 表达式
    source_object_ids JSON,                -- 依赖的对象 ID 列表
    
    -- 属性
    unit TEXT,                             -- 单位
    aggregation_type TEXT,                 -- 聚合类型
    dimensions JSON,                       -- 可切分维度
    
    -- 元信息
    tags JSON,
    status TEXT DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_metric_name ON metric_defs(name);
CREATE INDEX idx_metric_status ON metric_defs(status);
```

### 3.5 meta_events（元数据事件）—— 影澜轩

存储元数据变更事件流，提供审计和回溯能力。

```sql
CREATE TABLE meta_events (
    -- 主键
    id TEXT PRIMARY KEY,
    
    -- 时间
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 事件类型
    event_type TEXT NOT NULL,
    
    -- 关联对象
    object_id TEXT REFERENCES meta_objects(id),
    property_id TEXT REFERENCES meta_properties(id),
    
    -- 操作者
    actor_type TEXT NOT NULL,              -- user/ai/system
    actor_id TEXT,                         -- 操作者 ID
    
    -- 变更内容
    before_snapshot JSON,                  -- 变更前快照
    after_snapshot JSON,                   -- 变更后快照
    description TEXT                       -- 变更说明
);

-- 索引
CREATE INDEX idx_event_object ON meta_events(object_id);
CREATE INDEX idx_event_timestamp ON meta_events(timestamp);
CREATE INDEX idx_event_type ON meta_events(event_type);
CREATE INDEX idx_event_actor ON meta_events(actor_type, actor_id);
```

**event_type 枚举值：**

| 分类 | 值 | 说明 |
|------|---|------|
| 对象级别 | `objectCreated` | 对象创建 |
| | `objectUpdated` | 对象更新 |
| | `objectConfirmed` | 对象确认 |
| | `objectPublished` | 对象发布 |
| | `objectArchived` | 对象归档 |
| | `objectDeleted` | 对象删除 |
| 属性级别 | `propertyAdded` | 属性添加 |
| | `propertyUpdated` | 属性更新 |
| | `propertyRemoved` | 属性移除 |
| 关系级别 | `relationCreated` | 关系创建 |
| | `relationConfirmed` | 关系确认 |
| | `relationRemoved` | 关系移除 |
| 批量操作 | `bulkImport` | 批量导入 |
| | `bulkUpdate` | 批量更新 |

**actor_type 枚举值：**

| 值 | 说明 |
|---|------|
| `user` | 用户操作 |
| `ai` | AI 推断 |
| `system` | 系统自动 |

## 4. 初始化脚本

```sql
-- 完整的数据库初始化脚本
-- 版本: v0.1.0

-- ============================================
-- 星空座：元数据本体表
-- ============================================

CREATE TABLE IF NOT EXISTS meta_objects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    original_name TEXT NOT NULL,
    object_type TEXT NOT NULL,
    description TEXT,
    file_path TEXT,
    row_count INTEGER,
    status TEXT DEFAULT 'draft',
    tags JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    confirmed_at DATETIME,
    confirmed_by TEXT
);

CREATE TABLE IF NOT EXISTS meta_properties (
    id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL REFERENCES meta_objects(id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    sample_values JSON,
    null_count INTEGER DEFAULT 0,
    unique_count INTEGER DEFAULT 0,
    display_name TEXT,
    description TEXT,
    semantic_type TEXT,
    unit TEXT,
    format TEXT,
    business_rules TEXT,
    visual_preference JSON,
    ai_inferred JSON
);

CREATE TABLE IF NOT EXISTS meta_relations (
    id TEXT PRIMARY KEY,
    source_object_id TEXT NOT NULL REFERENCES meta_objects(id),
    source_property_id TEXT NOT NULL REFERENCES meta_properties(id),
    target_object_id TEXT NOT NULL REFERENCES meta_objects(id),
    target_property_id TEXT NOT NULL REFERENCES meta_properties(id),
    relation_type TEXT NOT NULL,
    relation_name TEXT,
    description TEXT,
    is_ai_inferred INTEGER DEFAULT 0,
    confidence REAL,
    is_confirmed INTEGER DEFAULT 0,
    confirmed_at DATETIME
);

CREATE TABLE IF NOT EXISTS metric_defs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    formula TEXT NOT NULL,
    source_object_ids JSON,
    unit TEXT,
    aggregation_type TEXT,
    dimensions JSON,
    tags JSON,
    status TEXT DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 影澜轩：变更事件流表
-- ============================================

CREATE TABLE IF NOT EXISTS meta_events (
    id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    object_id TEXT REFERENCES meta_objects(id),
    property_id TEXT REFERENCES meta_properties(id),
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    before_snapshot JSON,
    after_snapshot JSON,
    description TEXT
);

-- ============================================
-- 索引
-- ============================================

CREATE INDEX IF NOT EXISTS idx_object_status ON meta_objects(status);
CREATE INDEX IF NOT EXISTS idx_object_type ON meta_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_object_name ON meta_objects(name);

CREATE INDEX IF NOT EXISTS idx_prop_object ON meta_properties(object_id);
CREATE INDEX IF NOT EXISTS idx_prop_semantic ON meta_properties(semantic_type);

CREATE INDEX IF NOT EXISTS idx_relation_source ON meta_relations(source_object_id);
CREATE INDEX IF NOT EXISTS idx_relation_target ON meta_relations(target_object_id);
CREATE INDEX IF NOT EXISTS idx_relation_type ON meta_relations(relation_type);

CREATE INDEX IF NOT EXISTS idx_metric_name ON metric_defs(name);
CREATE INDEX IF NOT EXISTS idx_metric_status ON metric_defs(status);

CREATE INDEX IF NOT EXISTS idx_event_object ON meta_events(object_id);
CREATE INDEX IF NOT EXISTS idx_event_timestamp ON meta_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_event_type ON meta_events(event_type);
CREATE INDEX IF NOT EXISTS idx_event_actor ON meta_events(actor_type, actor_id);
```

## 5. 迁移策略

### 版本管理

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 迁移脚本命名

```
migrations/
├── 001_initial.sql           # 初始表结构
├── 002_add_metrics.sql       # 添加指标表
└── 003_add_indexes.sql       # 添加索引
```
