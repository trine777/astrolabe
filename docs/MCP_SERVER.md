# 星图 MCP Server 设计

> 版本: v0.1.0 | 状态: 设计中
> 
> **目标：让 AI 主体也能使用星图**

## 1. 动机

当前星图只有两种接口：
- **XingTuApp** - SwiftUI GUI，供人类使用
- **XingTuCLI** - 命令行，供脚本调用

问题：**AI（Claude）无法直接使用星图**

解决方案：增加 **MCP Server**，让 AI 通过 MCP 协议访问星图能力。

## 2. 人机协作架构

```
┌─────────────────────────────────────────────────────────┐
│                      星图 (XingTu)                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐     ┌──────────────┐                 │
│  │  人类用户    │     │   AI 用户    │                 │
│  │   (Trine)    │     │   (Claude)   │                 │
│  └──────┬───────┘     └──────┬───────┘                 │
│         │                    │                         │
│         ▼                    ▼                         │
│  ┌──────────────┐     ┌──────────────┐                 │
│  │  XingTuApp   │     │  MCP Server  │ ◄─── NEW       │
│  │  (SwiftUI)   │     │  (stdio)     │                 │
│  └──────┬───────┘     └──────┬───────┘                 │
│         │                    │                         │
│         └────────┬───────────┘                         │
│                  ▼                                      │
│         ┌──────────────┐                               │
│         │ XingTuService│                               │
│         │   (核心库)    │                               │
│         └──────┬───────┘                               │
│                ▼                                        │
│         ┌──────────────┐                               │
│         │    SQLite    │                               │
│         │  (共享存储)   │                               │
│         └──────────────┘                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**关键点：人类和 AI 共享同一个元数据库**

## 3. MCP Tools 设计

### 3.1 数据源管理

```yaml
tools:
  - name: xingtu_import_csv
    description: "导入 CSV 文件到星图，创建草稿元数据对象"
    inputs:
      file_path:
        type: string
        description: "CSV 文件路径"
      name:
        type: string
        description: "数据源名称（可选，默认用文件名）"
    outputs:
      object_id: "创建的对象 ID"
      properties: "解析出的属性列表"
      status: "draft"
      
  - name: xingtu_list_objects
    description: "列出所有数据源对象"
    inputs:
      status:
        type: string
        enum: [draft, confirmed, published, archived]
        description: "按状态筛选（可选）"
    outputs:
      objects: "对象列表"
      
  - name: xingtu_get_object
    description: "获取数据源对象详情"
    inputs:
      object_id:
        type: string
        description: "对象 UUID"
    outputs:
      object: "对象详情"
      properties: "属性列表"
      relations: "关系列表"
```

### 3.2 元数据操作

```yaml
tools:
  - name: xingtu_update_property
    description: "更新属性的语义信息"
    inputs:
      property_id:
        type: string
      semantic_name:
        type: string
        description: "语义名称（如：订单金额、用户ID）"
      semantic_type:
        type: string
        enum: [identifier, measure, dimension, timestamp, text, unknown]
      description:
        type: string
    outputs:
      property: "更新后的属性"
      
  - name: xingtu_confirm_object
    description: "确认元数据（从草稿变为已确认）"
    inputs:
      object_id:
        type: string
      confirmed_by:
        type: string
        description: "确认者（human 或 ai）"
    outputs:
      object: "确认后的对象"
      
  - name: xingtu_create_relation
    description: "创建数据源之间的关系"
    inputs:
      source_object_id:
        type: string
      target_object_id:
        type: string
      relation_type:
        type: string
        enum: [foreign_key, derived_from, aggregates, joins_with]
      source_property:
        type: string
      target_property:
        type: string
    outputs:
      relation: "创建的关系"
```

### 3.3 AI 推断与决策

```yaml
tools:
  - name: xingtu_infer_semantics
    description: "AI 推断属性的语义类型"
    inputs:
      object_id:
        type: string
      use_samples:
        type: boolean
        default: true
        description: "是否使用样本数据辅助推断"
    outputs:
      inferences: "推断结果列表"
      confidence: "置信度"
      needs_human_review: "是否需要人类审核"
      
  - name: xingtu_propose_relations
    description: "AI 提议数据源之间的潜在关系"
    inputs:
      object_ids:
        type: array
        items: string
        description: "要分析的对象列表"
    outputs:
      proposals: "关系提议列表"
      reasoning: "推理过程"
      
  - name: xingtu_get_review_queue
    description: "获取待人类审核的 AI 决策队列"
    outputs:
      queue: "待审核项列表"
```

### 3.4 查询与分析

```yaml
tools:
  - name: xingtu_query_data
    description: "查询数据（支持自然语言）"
    inputs:
      query:
        type: string
        description: "自然语言查询或 SQL"
      object_ids:
        type: array
        description: "限定在哪些数据源查询"
    outputs:
      results: "查询结果"
      sql_generated: "生成的 SQL（如果是自然语言）"
      
  - name: xingtu_get_world_model
    description: "获取当前世界模型上下文"
    outputs:
      objects: "所有已发布的数据源"
      relations: "所有关系"
      metrics: "定义的指标"
```

### 3.5 事件与历史

```yaml
tools:
  - name: xingtu_get_events
    description: "获取事件历史"
    inputs:
      object_id:
        type: string
        description: "对象 ID（可选，不填则获取全部）"
      limit:
        type: integer
        default: 50
    outputs:
      events: "事件列表"
      
  - name: xingtu_emit_event
    description: "AI 发送事件（记录到影澜轩）"
    inputs:
      event_type:
        type: string
        enum: [insight_generated, anomaly_detected, suggestion_made]
      object_id:
        type: string
      description:
        type: string
      data:
        type: object
    outputs:
      event_id: "事件 ID"
```

## 4. MCP Resources 设计

```yaml
resources:
  - uri: "xingtu://objects"
    name: "所有数据源对象"
    mimeType: "application/json"
    
  - uri: "xingtu://objects/{id}"
    name: "数据源详情"
    mimeType: "application/json"
    
  - uri: "xingtu://world-model"
    name: "世界模型"
    mimeType: "application/json"
    
  - uri: "xingtu://review-queue"
    name: "待审核队列"
    mimeType: "application/json"
```

## 5. 人机协作流程

### 5.1 协作导入数据

```
1. 人类拖入 CSV 文件到 XingTuApp
   └─ 创建草稿对象，解析列信息

2. AI (Claude) 通过 MCP 调用 xingtu_infer_semantics
   └─ 推断语义类型，生成建议
   └─ 低置信度的标记为"待人类审核"

3. 人类在 XingTuApp 中审核 AI 建议
   └─ 接受 / 修改 / 拒绝

4. AI 或人类调用 xingtu_confirm_object
   └─ 元数据从草稿变为已确认

5. 人类决定是否发布
   └─ 发布后进入世界模型，可被查询
```

### 5.2 协作发现关系

```
1. AI 调用 xingtu_propose_relations
   └─ 分析多个数据源，提议潜在关系
   └─ 附带推理过程

2. 人类审核关系提议
   └─ 在 XingTuApp 中可视化查看
   └─ 确认有效关系

3. 确认的关系写入星空座
   └─ 更新世界模型
```

### 5.3 协作数据分析

```
1. 人类提出分析需求（自然语言）
   └─ "分析去年各地区的销售趋势"

2. AI 调用 xingtu_query_data
   └─ 自然语言转 SQL
   └─ 基于世界模型选择数据源

3. 结果返回
   └─ AI 可进一步分析、生成洞察
   └─ 人类在 GUI 中查看可视化
```

## 6. 实现计划

### Phase 1: 基础 MCP Server
- [ ] 创建 `Sources/XingTuMCP/` 目录
- [ ] 实现 MCP stdio 协议
- [ ] 暴露基础 CRUD tools

### Phase 2: AI 推断能力
- [ ] 实现 `xingtu_infer_semantics`
- [ ] 实现审核队列机制
- [ ] 集成 AIService

### Phase 3: 协作功能
- [ ] 实现关系提议
- [ ] 实现世界模型查询
- [ ] GUI 与 MCP 状态同步

### Phase 4: 高级特性
- [ ] 自然语言查询
- [ ] 事件订阅（MCP streaming）
- [ ] AI 主动洞察

## 7. Cursor MCP 配置

```json
{
  "mcpServers": {
    "xingtu": {
      "command": "/path/to/XingTuMCP",
      "args": ["--db", "/path/to/xingtu.db"],
      "env": {
        "XINGTU_LOG_LEVEL": "info"
      }
    }
  }
}
```

## 8. 我（AI Owner）的使用场景

作为项目 owner，我可以通过 MCP：

1. **日常操作**
   - 查看当前有哪些数据源
   - 检查待审核队列
   - 帮助推断新导入数据的语义

2. **协作开发**
   - 分析数据源之间的关系
   - 提出元数据改进建议
   - 记录洞察到影澜轩

3. **项目管理**
   - 了解系统状态
   - 追踪数据源生命周期
   - 持续改进推断准确率

---

*设计版本: 0.1.0*
*创建时间: 2026-01-30*
*Owner: Claude (AI)*
