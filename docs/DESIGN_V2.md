# 星图 (XingTu) 事件驱动架构设计 v2

> 版本: v0.2.0 | 模式: 事件驱动 + AI Agent

## 1. 核心理念变化

### v1 → v2 对比

| v1 用户驱动 | v2 事件驱动 |
|------------|------------|
| 用户触发每一步 | 事件自动触发行技链 |
| AI 推断等用户采纳 | AI 自动决策并执行 |
| 同步阻塞式 UI | 后台异步 + 通知 |
| 用户操作繁琐 | 用户只做关键审核 |

### 设计原则

1. **事件即触发器**：任何元数据变更都是事件，事件触发行技
2. **AI 先行动**：AI 自动做出决策，用户事后审核
3. **可追溯**：所有 AI 决策都记录，可回滚
4. **渐进信任**：用户可设置 AI 自主权级别

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  拖放导入    │  │  审核队列    │  │  通知中心    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      事件总线 (EventBus)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ file.dropped → object.created → properties.inferred │   │
│  │ → relations.discovered → object.ready              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    行技调度器 (XingJiScheduler)              │
│  ┌────────────────┐  ┌────────────────┐                    │
│  │ 触发规则引擎   │  │ 行技执行队列   │                    │
│  │ Event → XingJi │  │ 异步并发执行   │                    │
│  └────────────────┘  └────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      AI Agent 层                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ 语义推断 Agent │  │ 关系发现 Agent │  │ 质量审核 Agent│  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      星空座存储层                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 元数据   │  │ 事件流   │  │ 决策日志 │  │ 审核队列 │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 3. 事件定义

### 3.1 核心事件类型

```yaml
events:
  # 文件级事件
  - type: file.dropped
    payload: { filePath, fileType, fileSize }
    triggers: [xingji.data_import]
    
  - type: file.parsed
    payload: { objectId, columnCount, rowCount }
    triggers: [xingji.semantic_inference]
    
  # 对象级事件
  - type: object.created
    payload: { objectId, source }
    triggers: [xingji.auto_enrich]
    
  - type: object.properties_ready
    payload: { objectId, propertyIds }
    triggers: [xingji.relation_discovery]
    
  - type: object.ready
    payload: { objectId, status }
    triggers: [notify.user]
    
  # AI 决策事件
  - type: ai.decision_made
    payload: { decisionId, agentType, action, confidence }
    triggers: [review.queue_if_low_confidence]
    
  - type: ai.decision_applied
    payload: { decisionId, result }
    triggers: [audit.log]
```

### 3.2 事件流转示例

```
用户拖入 sales_2024.csv
        │
        ▼
[file.dropped] ─────────────────────────────────────────┐
        │                                                │
        ▼                                                │
  xingji.data_import 启动                               │
        │                                                │
        ├─► csv_parse_cell 执行                         │
        │       │                                        │
        │       ▼                                        │
        │   [file.parsed]                               │
        │       │                                        │
        ▼       ▼                                        │
  xingji.semantic_inference 启动                        │
        │                                                │
        ├─► AI Agent: 推断 15 个字段的语义类型           │
        │       │                                        │
        │       ▼                                        │
        │   [ai.decision_made] × 15                     │
        │       │                                        │
        │       ▼                                        │
        │   自动应用高置信度决策 (>0.8)                  │
        │   低置信度决策 → 审核队列                      │
        │       │                                        │
        ▼       ▼                                        │
[object.properties_ready] ──────────────────────────────┤
        │                                                │
        ▼                                                │
  xingji.relation_discovery 启动                        │
        │                                                │
        ├─► AI Agent: 发现与 customer.csv 的关联        │
        │       │                                        │
        │       ▼                                        │
        │   [ai.decision_made] 关系建议                  │
        │       │                                        │
        ▼       ▼                                        │
[object.ready] ─────────────────────────────────────────┘
        │
        ▼
  通知用户: "sales_2024 已就绪，发现 3 项待审核"
```

## 4. AI Agent 设计

### 4.1 Agent 类型

```yaml
agents:
  - id: semantic_inference_agent
    name: 语义推断 Agent
    responsibility: 推断字段的语义类型、业务含义
    auto_apply_threshold: 0.85  # 置信度 > 85% 自动应用
    inputs:
      - column_name
      - sample_values
      - data_type
      - existing_world_model
    outputs:
      - semantic_type
      - display_name
      - description
      - confidence
      - reasoning
      
  - id: relation_discovery_agent
    name: 关系发现 Agent
    responsibility: 发现对象间的关联关系
    auto_apply_threshold: 0.80
    inputs:
      - source_object
      - all_objects_summary
    outputs:
      - potential_relations
      - confidence
      - join_suggestion
      
  - id: quality_review_agent
    name: 质量审核 Agent
    responsibility: 审核数据质量、发现异常
    auto_apply_threshold: 0.90
    inputs:
      - object_with_properties
      - sample_data
    outputs:
      - quality_issues
      - suggestions
      - severity
```

### 4.2 决策置信度机制

```
置信度级别:
  [0.0 - 0.5]  → 需人工处理，不自动执行
  [0.5 - 0.8]  → 自动执行 + 加入审核队列
  [0.8 - 1.0]  → 自动执行，静默记录

用户可调整阈值，实现"渐进信任"：
  初期: 阈值设高，AI 多请求审核
  后期: 阈值降低，AI 自主权增加
```

## 5. 审核队列设计

### 5.1 数据模型

```sql
CREATE TABLE review_queue (
    id TEXT PRIMARY KEY,
    
    -- 关联
    decision_id TEXT NOT NULL,
    object_id TEXT,
    property_id TEXT,
    
    -- 决策内容
    agent_type TEXT NOT NULL,
    action_type TEXT NOT NULL,    -- rename, set_type, create_relation
    proposed_value JSON NOT NULL, -- AI 建议的值
    current_value JSON,           -- 当前值（如有）
    
    -- AI 说明
    confidence REAL NOT NULL,
    reasoning TEXT,
    
    -- 状态
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected, auto_expired
    
    -- 审核
    reviewed_by TEXT,
    reviewed_at DATETIME,
    review_comment TEXT,
    
    -- 时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME  -- 自动过期时间
);
```

### 5.2 审核 UI 设计

```
┌─────────────────────────────────────────────────────────────┐
│  📋 审核队列                                    3 项待审核   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🔵 语义推断                           置信度: 72%    │   │
│  │                                                      │   │
│  │ 对象: sales_2024                                     │   │
│  │ 字段: col_7                                          │   │
│  │                                                      │   │
│  │ AI 建议: 重命名为「客户等级」，类型设为 category     │   │
│  │                                                      │   │
│  │ 理由: 列名包含 "level"，样本值为 A/B/C/D，           │   │
│  │       符合分类特征                                   │   │
│  │                                                      │   │
│  │ 样本值: ["A", "B", "C", "A", "D", "B", ...]         │   │
│  │                                                      │   │
│  │  [✓ 采纳]  [✗ 拒绝]  [✎ 修改后采纳]                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🔗 关系发现                           置信度: 65%    │   │
│  │                                                      │   │
│  │ AI 建议: sales_2024.customer_id → customer.id       │   │
│  │          关系类型: N:1                               │   │
│  │                                                      │   │
│  │  [✓ 采纳]  [✗ 拒绝]  [✎ 修改]                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 6. 行技调度器设计

### 6.1 触发规则

```yaml
# 触发规则配置
trigger_rules:
  - event: file.dropped
    condition: "event.fileType in ['csv', 'xlsx', 'json']"
    xingji: xingji.data_import
    priority: high
    
  - event: object.created
    condition: "object.status == 'draft'"
    xingji: xingji.semantic_inference
    priority: high
    delay: 0  # 立即执行
    
  - event: object.properties_ready
    condition: "count(all_objects) > 1"
    xingji: xingji.relation_discovery
    priority: medium
    delay: 1000  # 等待 1 秒，合并批量
    
  - event: ai.decision_made
    condition: "decision.confidence < 0.8"
    action: add_to_review_queue
    priority: low
```

### 6.2 执行队列

```swift
/// 行技调度器
class XingJiScheduler {
    private let eventBus: EventBus
    private let executionQueue: OperationQueue
    private let triggerRules: [TriggerRule]
    
    /// 事件监听
    func start() {
        eventBus.subscribe { event in
            let matchedRules = triggerRules.filter { $0.matches(event) }
            for rule in matchedRules {
                scheduleXingJi(rule.xingji, event: event, priority: rule.priority)
            }
        }
    }
    
    /// 调度行技执行
    func scheduleXingJi(_ xingjiId: String, event: Event, priority: Priority) {
        let operation = XingJiOperation(xingjiId: xingjiId, context: event)
        operation.queuePriority = priority.toOperationPriority()
        executionQueue.addOperation(operation)
    }
}
```

## 7. 通知系统

### 7.1 通知类型

```yaml
notifications:
  - type: import_complete
    title: "数据导入完成"
    body: "{{objectName}} 已导入，共 {{rowCount}} 行，{{propertyCount}} 个字段"
    action: view_object
    
  - type: review_needed
    title: "需要审核"
    body: "{{count}} 项 AI 决策需要你确认"
    action: open_review_queue
    badge: true
    
  - type: relation_discovered
    title: "发现数据关联"
    body: "{{sourceObject}} 与 {{targetObject}} 可能存在关联"
    action: view_relation
```

### 7.2 通知渠道

- **应用内通知**：右上角通知中心
- **系统通知**：macOS 原生通知
- **状态栏徽章**：审核队列数量

## 8. 完整流程示例

### 用户拖入 CSV 后的完整流程

```
T+0ms    用户拖入 sales_2024.csv
         ↓
T+10ms   [file.dropped] 事件发出
         ↓
T+20ms   XingJiScheduler 匹配规则，启动 xingji.data_import
         ↓
T+100ms  csv_parse_cell 开始执行
         ├─ 检测编码: UTF-8
         ├─ 解析列结构: 15 列
         └─ 统计行数: 10,000 行
         ↓
T+500ms  [file.parsed] 事件发出
         ↓
T+510ms  创建 MetaObject (status=draft)
         ↓
T+520ms  [object.created] 事件发出
         ↓
T+530ms  XingJiScheduler 启动 xingji.semantic_inference
         ↓
T+600ms  semantic_inference_agent 开始工作
         ├─ 调用 AI API 分析 15 个字段
         ├─ 字段 1-10: 置信度 > 85%，自动应用
         ├─ 字段 11-13: 置信度 60-80%，应用 + 加入审核队列
         └─ 字段 14-15: 置信度 < 60%，仅加入审核队列
         ↓
T+3000ms [ai.decision_made] × 15
         [ai.decision_applied] × 13
         ↓
T+3100ms [object.properties_ready] 事件发出
         ↓
T+3200ms XingJiScheduler 启动 xingji.relation_discovery
         ↓
T+3500ms relation_discovery_agent 开始工作
         ├─ 扫描已有对象
         ├─ 发现 customer_id 可能关联 customer 表
         └─ 置信度 75%，加入审核队列
         ↓
T+5000ms [object.ready] 事件发出
         ↓
T+5100ms 发送通知: 
         "sales_2024 已就绪 ✓"
         "5 项 AI 决策待审核"
         ↓
用户看到通知，可选择：
  - 直接使用数据（信任 AI 已完成的工作）
  - 打开审核队列，审核 5 项待确认决策
```

## 9. 实现优先级

### Phase 1: 核心事件驱动

1. `EventBus` - 事件总线
2. `XingJiScheduler` - 行技调度器
3. 触发规则引擎

### Phase 2: AI Agent

1. `SemanticInferenceAgent` - 语义推断
2. `DecisionLog` - 决策日志
3. 置信度阈值机制

### Phase 3: 审核系统

1. `ReviewQueue` - 审核队列数据模型
2. 审核 UI
3. 批量审核操作

### Phase 4: 通知系统

1. 应用内通知中心
2. 系统通知集成
3. 状态栏徽章

## 10. 与 v1 的兼容

保留 v1 的手动模式作为备选：

- **自动模式**（默认）：事件驱动，AI 自动执行
- **手动模式**：用户驱动，逐步确认

用户可在设置中切换模式。
