# 星图 (XingTu) 事件驱动胞式与行技 v2

> 版本: v0.2.0 | 模式: 事件驱动 + AI Agent

## 1. 事件驱动架构核心组件

### 1.1 事件总线 (EventBus)

```yaml
id: event_bus
name: 事件总线
description: 所有事件的发布/订阅中心

capabilities:
  - publish: 发布事件
  - subscribe: 订阅事件
  - filter: 事件过滤
  - replay: 事件回放（调试用）

event_schema:
  id: UUID
  type: String          # 事件类型
  timestamp: DateTime
  source: String        # 来源组件
  payload: JSON         # 事件数据
  correlation_id: UUID  # 关联 ID（追踪事件链）
```

### 1.2 行技调度器 (XingJiScheduler)

```yaml
id: xingji_scheduler
name: 行技调度器
description: 监听事件，匹配规则，调度行技执行

capabilities:
  - match_rules: 事件匹配触发规则
  - schedule: 调度行技到执行队列
  - prioritize: 优先级管理
  - batch: 批量合并执行
  - retry: 失败重试

config:
  max_concurrent: 5       # 最大并发行技数
  default_timeout: 60000  # 默认超时 60s
  retry_attempts: 3       # 重试次数
```

## 2. 核心事件定义

### 2.1 文件事件

```yaml
# 文件拖入
- type: file.dropped
  source: ui.drop_zone
  payload:
    file_path: String
    file_type: String    # csv, xlsx, json
    file_size: Int
    file_name: String
  triggers:
    - xingji.auto_import

# 文件解析完成
- type: file.parsed
  source: csv_parse_cell
  payload:
    object_id: UUID
    column_count: Int
    row_count: Int
    encoding: String
    parse_duration_ms: Int
  triggers:
    - xingji.semantic_inference
```

### 2.2 对象事件

```yaml
# 对象创建
- type: object.created
  source: meta_store
  payload:
    object_id: UUID
    object_name: String
    object_type: String
    source_file: String
  triggers:
    - xingji.auto_enrich

# 属性就绪
- type: object.properties_ready
  source: semantic_inference_agent
  payload:
    object_id: UUID
    property_count: Int
    auto_applied_count: Int
    pending_review_count: Int
  triggers:
    - xingji.relation_discovery

# 对象就绪（所有自动处理完成）
- type: object.ready
  source: xingji_scheduler
  payload:
    object_id: UUID
    object_name: String
    total_properties: Int
    pending_reviews: Int
    discovered_relations: Int
  triggers:
    - notify.import_complete
```

### 2.3 AI 决策事件

```yaml
# AI 做出决策
- type: ai.decision_made
  source: agent.*
  payload:
    decision_id: UUID
    agent_type: String     # semantic_inference, relation_discovery
    object_id: UUID
    property_id: UUID?
    action_type: String    # rename, set_type, create_relation
    proposed_value: JSON
    confidence: Float
    reasoning: String
  triggers:
    - conditional:
        - if: confidence >= 0.85
          action: auto_apply
        - if: confidence >= 0.5
          action: apply_and_queue_review
        - else:
          action: queue_review_only

# AI 决策已应用
- type: ai.decision_applied
  source: decision_executor
  payload:
    decision_id: UUID
    applied_at: DateTime
    was_auto: Boolean
  triggers:
    - audit.log
```

### 2.4 审核事件

```yaml
# 审核项创建
- type: review.created
  source: review_queue
  payload:
    review_id: UUID
    decision_id: UUID
    agent_type: String
    confidence: Float
  triggers:
    - notify.review_needed (batched)

# 审核完成
- type: review.completed
  source: review_queue
  payload:
    review_id: UUID
    decision_id: UUID
    action: String   # approved, rejected, modified
    modified_value: JSON?
  triggers:
    - apply_or_rollback
```

## 3. AI Agent 胞式

### 3.1 semantic_inference_agent（语义推断 Agent）

```yaml
id: semantic_inference_agent
name: 语义推断 Agent
version: 0.2.0
description: 自动推断字段的语义类型、业务名称和描述

# 器官钉
organ_pins:
  - organ: 星空座
    role: context_provider
    action: get_world_model_context
    
  - organ: 影澜轩
    role: decision_logger
    action: log_ai_decision

# 机械钉
mech_pins:
  - type: http
    level: L1
    action: call_llm
    params:
      model: qwen-plus
      temperature: 0.2
      
# 输入
input:
  - name: object
    type: MetaObject
    
  - name: properties
    type: "[MetaProperty]"
    
  - name: world_context
    type: WorldModelContext

# 输出（每个属性一个决策）
output:
  - name: decisions
    type: "[AIDecision]"
    schema:
      property_id: UUID
      action_type: "rename|set_type|set_description|set_unit"
      proposed_value: String
      confidence: Float
      reasoning: String

# 置信度阈值配置
confidence_config:
  auto_apply_threshold: 0.85
  review_threshold: 0.50
  
# Prompt 模板
prompt_template: |
  你是一个数据语义分析专家。请分析以下数据字段，推断其业务含义。

  ## 当前对象
  名称: {{object.name}}
  描述: {{object.description}}
  
  ## 已有世界模型（参考）
  {{world_context}}
  
  ## 待分析字段
  {{#each properties}}
  ### 字段 {{@index}}
  - 原始名称: {{this.original_name}}
  - 数据类型: {{this.data_type}}
  - 样本值: {{this.sample_values}}
  - 空值率: {{this.null_rate}}
  - 唯一值数: {{this.unique_count}}
  {{/each}}
  
  ## 输出要求
  对每个字段，输出 JSON 数组：
  ```json
  [
    {
      "property_id": "原始名称",
      "display_name": "推断的业务名称",
      "semantic_type": "语义类型枚举值",
      "description": "业务含义描述",
      "confidence": 0.0-1.0,
      "reasoning": "推断理由"
    }
  ]
  ```
  
  语义类型枚举: primaryKey, foreignKey, uniqueId, personName, orgName, 
  productName, email, phone, address, amount, quantity, percentage, 
  timestamp, dateOnly, category, status, tag, freeText
```

### 3.2 relation_discovery_agent（关系发现 Agent）

```yaml
id: relation_discovery_agent
name: 关系发现 Agent
version: 0.2.0
description: 自动发现数据对象之间的关联关系

# 器官钉
organ_pins:
  - organ: 星空座
    role: graph_builder
    action: get_all_objects_summary
    
  - organ: 影澜轩
    role: decision_logger
    action: log_ai_decision

# 机械钉
mech_pins:
  - type: http
    level: L1
    action: call_llm
    params:
      model: qwen-plus
      
# 输入
input:
  - name: source_object
    type: MetaObject
    
  - name: source_properties
    type: "[MetaProperty]"
    
  - name: all_objects
    type: "[MetaObjectSummary]"

# 输出
output:
  - name: relations
    type: "[RelationSuggestion]"
    schema:
      source_property_id: UUID
      target_object_id: UUID
      target_property_id: UUID
      relation_type: "oneToOne|oneToMany|manyToOne|manyToMany"
      relation_name: String
      confidence: Float
      reasoning: String
      join_hint: String  # SQL JOIN 建议

# Prompt 模板
prompt_template: |
  你是一个数据建模专家。请分析数据对象之间的可能关联。
  
  ## 当前对象
  名称: {{source_object.name}}
  字段列表:
  {{#each source_properties}}
  - {{this.display_name}} ({{this.original_name}}): {{this.semantic_type}}
  {{/each}}
  
  ## 已有对象
  {{#each all_objects}}
  ### {{this.name}}
  字段: {{this.property_names}}
  {{/each}}
  
  ## 输出要求
  找出可能的外键关系，输出 JSON：
  ```json
  [
    {
      "source_property": "当前对象的字段名",
      "target_object": "目标对象名",
      "target_property": "目标字段名",
      "relation_type": "manyToOne",
      "relation_name": "关系描述",
      "confidence": 0.0-1.0,
      "reasoning": "推断理由",
      "join_hint": "JOIN customer ON sales.customer_id = customer.id"
    }
  ]
  ```
```

### 3.3 quality_review_agent（质量审核 Agent）

```yaml
id: quality_review_agent
name: 质量审核 Agent
version: 0.2.0
description: 自动审核数据质量，发现异常和问题

# 输入
input:
  - name: object
    type: MetaObject
  - name: properties
    type: "[MetaProperty]"
  - name: sample_data
    type: "[[String]]"

# 输出
output:
  - name: issues
    type: "[QualityIssue]"
    schema:
      property_id: UUID?
      issue_type: "missing_values|inconsistent_format|outliers|duplicates"
      severity: "info|warning|error"
      description: String
      suggestion: String
      affected_rows: Int
```

## 4. 事件驱动行技

### 4.1 xingji.auto_import（自动导入行技）

```yaml
id: xingji.auto_import
name: 自动导入行技
version: 0.2.0
description: 文件拖入后自动执行的完整导入流程

trigger:
  event: file.dropped
  condition: "event.file_type in ['csv', 'xlsx', 'json']"

# 组成胞式
cells:
  - csv_parse_cell
  - object_create_cell

# 流程
flow:
  type: sequential
  steps:
    - id: parse
      cell: csv_parse_cell
      on_success: emit(file.parsed)
      on_failure: emit(import.failed)
      
    - id: create_object
      cell: object_create_cell
      input_mapping:
        parse_result: "{{parse.output}}"
      on_success: emit(object.created)

# 超时
timeout_ms: 30000
```

### 4.2 xingji.semantic_inference（语义推断行技）

```yaml
id: xingji.semantic_inference
name: 语义推断行技
version: 0.2.0
description: 对象创建后自动推断所有字段的语义

trigger:
  event: object.created
  condition: "object.status == 'draft'"

# 组成
cells:
  - semantic_inference_agent
  - decision_executor_cell

# 流程
flow:
  type: sequential
  steps:
    - id: infer
      cell: semantic_inference_agent
      
    - id: process_decisions
      cell: decision_executor_cell
      input_mapping:
        decisions: "{{infer.output.decisions}}"
      # 对每个决策：
      # - confidence >= 0.85: 自动应用，emit(ai.decision_applied)
      # - confidence >= 0.50: 应用 + 加入审核队列
      # - confidence < 0.50: 仅加入审核队列
      
    - id: complete
      action: emit(object.properties_ready)
```

### 4.3 xingji.relation_discovery（关系发现行技）

```yaml
id: xingji.relation_discovery
name: 关系发现行技
version: 0.2.0
description: 属性就绪后自动发现对象间关系

trigger:
  event: object.properties_ready
  condition: "count(all_objects) > 1"  # 至少有 2 个对象才有意义
  delay_ms: 1000  # 延迟 1 秒，等待批量

# 组成
cells:
  - relation_discovery_agent
  - decision_executor_cell

# 流程
flow:
  type: sequential
  steps:
    - id: discover
      cell: relation_discovery_agent
      
    - id: process_relations
      cell: decision_executor_cell
      input_mapping:
        decisions: "{{discover.output.relations}}"
        
    - id: complete
      action: emit(object.ready)
```

## 5. 决策执行器

### 5.1 decision_executor_cell

```yaml
id: decision_executor_cell
name: 决策执行器胞式
version: 0.2.0
description: 根据置信度阈值执行或排队 AI 决策

input:
  - name: decisions
    type: "[AIDecision]"
  - name: config
    type: DecisionConfig
    default:
      auto_apply_threshold: 0.85
      review_threshold: 0.50

logic: |
  for decision in decisions:
    if decision.confidence >= config.auto_apply_threshold:
      apply_decision(decision)
      emit(ai.decision_applied, {was_auto: true})
      
    elif decision.confidence >= config.review_threshold:
      apply_decision(decision)
      add_to_review_queue(decision)
      emit(ai.decision_applied, {was_auto: true, pending_review: true})
      
    else:
      add_to_review_queue(decision)
      emit(review.created)

output:
  - name: applied_count
    type: Int
  - name: queued_count
    type: Int
```

## 6. 触发规则引擎

### 6.1 规则定义格式

```yaml
# trigger_rules.yaml
rules:
  - id: rule_auto_import
    name: 文件自动导入
    event_type: file.dropped
    condition:
      operator: in
      field: payload.file_type
      values: [csv, xlsx, json]
    action:
      type: start_xingji
      xingji_id: xingji.auto_import
    priority: high
    enabled: true
    
  - id: rule_semantic_inference
    name: 自动语义推断
    event_type: object.created
    condition:
      operator: eq
      field: payload.status
      value: draft
    action:
      type: start_xingji
      xingji_id: xingji.semantic_inference
    priority: high
    delay_ms: 0
    
  - id: rule_relation_discovery
    name: 自动关系发现
    event_type: object.properties_ready
    condition:
      operator: gt
      field: "count(objects)"
      value: 1
    action:
      type: start_xingji
      xingji_id: xingji.relation_discovery
    priority: medium
    delay_ms: 1000
    batch_window_ms: 2000  # 2 秒内的事件合并
    
  - id: rule_low_confidence_review
    name: 低置信度进审核
    event_type: ai.decision_made
    condition:
      operator: lt
      field: payload.confidence
      value: 0.85
    action:
      type: add_to_review_queue
    priority: low
```

## 7. 审核队列胞式

### 7.1 review_queue_cell

```yaml
id: review_queue_cell
name: 审核队列胞式
version: 0.2.0
description: 管理待审核的 AI 决策

operations:
  - add:
      input: AIDecision
      output: ReviewItem
      
  - approve:
      input: review_id
      action: apply_decision
      emit: review.completed(approved)
      
  - reject:
      input: review_id
      action: rollback_if_applied
      emit: review.completed(rejected)
      
  - modify:
      input: {review_id, modified_value}
      action: apply_modified
      emit: review.completed(modified)
      
  - batch_approve:
      input: "[review_id]"
      action: bulk_apply
      
  - auto_expire:
      condition: "now > expires_at"
      action: mark_expired
```

## 8. 通知胞式

### 8.1 notify_cell

```yaml
id: notify_cell
name: 通知胞式
version: 0.2.0
description: 发送用户通知

triggers:
  - event: object.ready
    template: import_complete
    
  - event: review.created
    template: review_needed
    batch_window_ms: 5000  # 5 秒内合并

templates:
  import_complete:
    title: "✓ {{object_name}} 已就绪"
    body: "共 {{row_count}} 行，{{property_count}} 个字段"
    subtitle: "{{pending_reviews}} 项待审核"
    action: open_object
    
  review_needed:
    title: "📋 {{count}} 项待审核"
    body: "AI 有 {{count}} 个决策需要你确认"
    action: open_review_queue
    badge: true

channels:
  - in_app: true
  - system_notification: true
  - status_bar_badge: true
```

## 9. 实现路线图

### Phase 1: 事件驱动基础

```
Week 1:
├── EventBus 实现
├── XingJiScheduler 实现
├── 触发规则引擎
└── 基础事件类型

Week 2:
├── 事件持久化
├── 事件回放（调试）
└── 事件链追踪
```

### Phase 2: AI Agent

```
Week 3:
├── semantic_inference_agent
├── 决策日志
└── 置信度机制

Week 4:
├── relation_discovery_agent
├── quality_review_agent
└── Agent 配置 UI
```

### Phase 3: 审核系统

```
Week 5:
├── ReviewQueue 数据模型
├── 审核 UI
├── 批量操作

Week 6:
├── 审核历史
├── 决策回滚
└── 审核统计
```

### Phase 4: 通知系统

```
Week 7:
├── 应用内通知
├── 系统通知
├── 状态栏徽章
└── 通知偏好设置
```
