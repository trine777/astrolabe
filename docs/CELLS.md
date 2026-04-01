# 星图 (XingTu) 胞式与行技定义

> 版本: v0.1.0 | 层级: 胞式层 + 行技层

## 1. 概述

### 1.1 胞式（Cell）

胞式是风隐 OS 的最小"意图 → 动作"结构，由：
- **器官钉（Organ-Pin）**：定义需要哪些器官参与
- **机械钉（Mech-Pin）**：定义需要调用哪些执行器

组合而成。

### 1.2 行技（XingJi）

行技 = 胞式串联成的完整能力。一个行技就是一个"完整技能"。

### 1.3 命名规范

```
胞式: {domain}_{action}_cell
行技: xingji.{domain}_{skill}_v{version}
```

## 2. 星图胞式定义

### 2.1 csv_parse_cell（CSV 解析胞式）

**功能**：解析 CSV 文件，提取结构信息

```yaml
# cells/csv_parse_cell.yaml
id: csv_parse_cell
name: CSV 解析胞式
version: 0.1.0
description: 解析 CSV 文件，提取列结构、数据类型和样本数据

# 器官钉：定义参与的器官
organ_pins:
  - organ: 语界枢
    role: input_receiver
    action: receive_file
    description: 接收用户拖入的文件

# 机械钉：定义调用的执行器
mech_pins:
  - type: file_io
    level: L0
    action: read_csv
    params:
      encoding: auto_detect    # 自动检测编码
      delimiter: auto_detect   # 自动检测分隔符
      preview_rows: 100        # 预览行数
      max_sample_values: 10    # 每列最大样本数

# 输入契约
input:
  - name: file_url
    type: URL
    required: true
    description: CSV 文件路径

# 输出契约
output:
  - name: columns
    type: "[ColumnInfo]"
    description: 列信息数组
    
  - name: row_count
    type: Int
    description: 数据行数
    
  - name: sample_data
    type: "[[String]]"
    description: 样本数据
    
  - name: encoding
    type: String
    description: 检测到的编码

# 错误处理
errors:
  - code: E001
    condition: file_not_found
    message: 文件不存在
    
  - code: E002
    condition: unsupported_format
    message: 不支持的文件格式
    
  - code: E003
    condition: parse_failed
    message: CSV 解析失败

# 能量消耗（炽心核计量）
energy:
  base_cost: 1
  per_mb_cost: 0.5
```

### 2.2 meta_infer_cell（元数据推断胞式）

**功能**：使用 AI 推断列的语义类型

```yaml
# cells/meta_infer_cell.yaml
id: meta_infer_cell
name: 元数据推断胞式
version: 0.1.0
description: 调用 AI 分析数据结构，推断语义类型和业务含义

# 器官钉
organ_pins:
  - organ: 星空座
    role: context_provider
    action: provide_world_model_context
    description: 提供已有世界模型作为上下文
    
  - organ: 影澜轩
    role: observer
    action: observe_inference
    description: 观察 AI 推断过程，记录洞察

# 机械钉
mech_pins:
  - type: http
    level: L0
    action: call_llm
    params:
      endpoint: openai_api  # 或 claude_api
      model: gpt-4
      temperature: 0.3
      max_tokens: 2000
      prompt_template: meta_inference_v1

# 输入契约
input:
  - name: schema_info
    type: SchemaInfo
    required: true
    description: 数据结构信息（来自 csv_parse_cell）
    
  - name: existing_objects
    type: "[MetaObject]"
    required: false
    description: 已有的元数据对象（用于关系推断）

# 输出契约
output:
  - name: object_suggestion
    type: ObjectSuggestion
    description: 对象命名和描述建议
    
  - name: property_suggestions
    type: "[PropertySuggestion]"
    description: 每列的语义类型和业务含义建议
    
  - name: potential_relations
    type: "[RelationSuggestion]"
    description: 可能的关系建议
    
  - name: data_quality_notes
    type: "[String]"
    description: 数据质量观察

# 能量消耗
energy:
  base_cost: 5
  per_column_cost: 0.5
```

### 2.3 meta_confirm_cell（元数据确认胞式）

**功能**：用户确认/修改元数据，写入星空座

```yaml
# cells/meta_confirm_cell.yaml
id: meta_confirm_cell
name: 元数据确认胞式
version: 0.1.0
description: 用户确认或修改 AI 推断的元数据，写入星空座世界模型

# 器官钉
organ_pins:
  - organ: 语界枢
    role: ui_presenter
    action: present_editor_ui
    description: 呈现元数据编辑界面
    
  - organ: 星空座
    role: storage
    action: store_confirmed_meta
    description: 存储确认后的元数据
    
  - organ: 影澜轩
    role: event_emitter
    action: emit_confirmation_event
    description: 发送确认事件到事件流

# 输入契约
input:
  - name: draft_object
    type: MetaObject
    required: true
    description: AI 推断的草稿对象
    
  - name: user_edits
    type: "[MetaEdit]"
    required: false
    description: 用户的修改

# 输出契约
output:
  - name: confirmed_object
    type: MetaObject
    description: 确认后的元数据对象
    
  - name: event_id
    type: UUID
    description: 确认事件 ID

# 状态转换
state_transition:
  from: draft
  to: confirmed
  condition: user_confirms

# 能量消耗
energy:
  base_cost: 1
```

### 2.4 query_execute_cell（查询执行胞式）

**功能**：基于世界模型执行数据查询

```yaml
# cells/query_execute_cell.yaml
id: query_execute_cell
name: 查询执行胞式
version: 0.1.0
description: 解析查询意图并执行，支持自然语言和 SQL

# 器官钉
organ_pins:
  - organ: 星空座
    role: semantic_resolver
    action: resolve_semantic_query
    description: 使用世界模型解析查询语义
    
  - organ: 炽心核
    role: authorizer
    action: authorize_execution
    description: 审批执行权限，控制能量消耗
    
  - organ: 影澜轩
    role: logger
    action: log_query_result
    description: 记录查询结果和洞察

# 机械钉
mech_pins:
  - type: sql
    level: L0
    action: execute
    params:
      timeout_ms: 30000
      max_rows: 10000

# 输入契约
input:
  - name: query
    type: String
    required: true
    description: 查询语句（自然语言或 SQL）
    
  - name: query_type
    type: QueryType  # nl | sql
    required: true
    description: 查询类型
    
  - name: context
    type: QueryContext
    required: false
    description: 查询上下文

# 输出契约
output:
  - name: result_set
    type: DataFrame
    description: 查询结果
    
  - name: execution_stats
    type: ExecutionStats
    description: 执行统计（耗时、扫描行数等）

# 能量消耗
energy:
  base_cost: 2
  per_1k_rows_cost: 0.1
```

### 2.5 relation_resolve_cell（关系解析胞式）

**功能**：解析对象间的关系，构建语义图谱

```yaml
# cells/relation_resolve_cell.yaml
id: relation_resolve_cell
name: 关系解析胞式
version: 0.1.0
description: 分析多个数据对象，推断并建立关系

# 器官钉
organ_pins:
  - organ: 星空座
    role: graph_builder
    action: build_semantic_graph
    description: 构建语义图谱
    
  - organ: 影澜轩
    role: observer
    action: observe_relation_discovery
    description: 观察关系发现过程

# 机械钉
mech_pins:
  - type: http
    level: L0
    action: call_llm
    params:
      model: gpt-4
      prompt_template: relation_inference_v1

# 输入契约
input:
  - name: objects
    type: "[MetaObject]"
    required: true
    description: 要分析关系的对象列表

# 输出契约
output:
  - name: relations
    type: "[MetaRelation]"
    description: 推断出的关系列表
    
  - name: graph_summary
    type: GraphSummary
    description: 图谱摘要

# 能量消耗
energy:
  base_cost: 3
  per_object_cost: 1
```

## 3. 星图行技定义

### 3.1 xingji.data_import_v0（数据导入行技）

**功能**：完整的 CSV 数据导入流程

```yaml
# xingji/data_import_v0.yaml
id: xingji.data_import_v0
name: 数据导入行技
version: 0.1.0
description: 完整的 CSV 数据导入流程，包含解析、AI 推断、用户确认

# 组成胞式
cells:
  - csv_parse_cell
  - meta_infer_cell
  - meta_confirm_cell

# 流程定义
flow:
  type: sequential
  steps:
    - id: parse
      cell: csv_parse_cell
      on_success: infer
      on_failure: abort
      error_message: "文件解析失败"
      
    - id: infer
      cell: meta_infer_cell
      input_mapping:
        schema_info: "{{parse.output}}"
      on_success: confirm
      on_failure: skip_to_confirm  # AI 失败时跳过推断，让用户手动填写
      
    - id: confirm
      cell: meta_confirm_cell
      input_mapping:
        draft_object: "{{infer.output.object_suggestion}}"
      on_success: complete
      on_failure: retry
      max_retries: 3

# 输入契约
input_contract:
  - name: file_url
    type: URL
    required: true
    description: CSV 文件路径
    
  - name: import_options
    type: ImportOptions
    required: false
    description: 导入选项

# 输出契约
output_contract:
  - name: object_id
    type: UUID
    description: 创建的元数据对象 ID
    
  - name: status
    type: ImportStatus
    description: 导入状态

# 标签
tags:
  - 数据导入
  - CSV
  - 元数据
  - Flow City

# 适用局谱
suitable_jups:
  - 数据准备
  - 业务建模

# 能量消耗估算
energy_estimate:
  min: 7
  max: 20
  factors:
    - 文件大小
    - 列数量
    - AI 调用次数
```

### 3.2 xingji.meta_analysis_v0（元数据分析行技）

**功能**：对已有元数据进行深度分析

```yaml
# xingji/meta_analysis_v0.yaml
id: xingji.meta_analysis_v0
name: 元数据分析行技
version: 0.1.0
description: 对已有元数据对象进行深度分析，发现关系和模式

# 组成胞式
cells:
  - relation_resolve_cell
  - meta_infer_cell

# 流程定义
flow:
  type: sequential
  steps:
    - id: resolve_relations
      cell: relation_resolve_cell
      
    - id: enrich_metadata
      cell: meta_infer_cell
      condition: "{{resolve_relations.output.relations.length > 0}}"

# 输入契约
input_contract:
  - name: object_ids
    type: "[UUID]"
    required: true
    description: 要分析的对象 ID 列表

# 输出契约
output_contract:
  - name: relations
    type: "[MetaRelation]"
    description: 发现的关系
    
  - name: insights
    type: "[Insight]"
    description: 分析洞察

# 标签
tags:
  - 元数据分析
  - 关系发现
  - 语义图谱
```

### 3.3 xingji.cross_data_query_v0（跨数据联动查询行技）

**功能**：基于世界模型的多数据源联动查询

```yaml
# xingji/cross_data_query_v0.yaml
id: xingji.cross_data_query_v0
name: 跨数据联动查询行技
version: 0.1.0
description: 使用自然语言进行跨数据源联动查询

# 组成胞式
cells:
  - nl_parse_cell        # 自然语言解析（待定义）
  - relation_resolve_cell
  - query_execute_cell
  - result_visualize_cell # 结果可视化（待定义）

# 流程定义
flow:
  type: sequential
  steps:
    - id: parse_query
      cell: nl_parse_cell
      
    - id: resolve_relations
      cell: relation_resolve_cell
      input_mapping:
        objects: "{{parse_query.output.referenced_objects}}"
      
    - id: execute
      cell: query_execute_cell
      input_mapping:
        query: "{{parse_query.output.sql}}"
        query_type: sql
        
    - id: visualize
      cell: result_visualize_cell
      input_mapping:
        result_set: "{{execute.output.result_set}}"
      condition: "{{execute.output.result_set.row_count > 0}}"

# 输入契约
input_contract:
  - name: natural_language_query
    type: String
    required: true
    description: 自然语言查询
    
  - name: target_objects
    type: "[UUID]"
    required: false
    description: 限定查询范围的对象

# 输出契约
output_contract:
  - name: result
    type: QueryResult
    description: 查询结果
    
  - name: visualization
    type: ChartSpec
    description: 可视化规格
    
  - name: insight
    type: String
    description: 自动生成的洞察

# 标签
tags:
  - 数据分析
  - 联动查询
  - 自然语言
  - 可视化

# 能量消耗估算
energy_estimate:
  min: 5
  max: 15
```

## 4. 胞式与行技的 formed 产物

当胞式/行技经过 Flow City 试炼成熟后，将输出到 formed：

```
flow-city/formed/data/
├── xingtu.data_import.manual.md      # 数据导入手册
├── xingtu.data_import.skill.scl      # 导入技能 SCL
├── xingtu.cross_query.manual.md      # 联动查询手册
├── xingtu.cross_query.skill.scl      # 查询技能 SCL
└── xingtu.cells/                     # 胞式模板
    ├── csv_parse_cell.yaml
    ├── meta_infer_cell.yaml
    └── query_execute_cell.yaml
```

## 5. 胞式组合规则

```
胞式 = Σ(器官钉) + Σ(机械钉)

原则：
1. 每个胞式必须有明确的输入/输出契约
2. 器官钉定义"这个动作需要哪些器官参与"
3. 机械钉定义"这个动作需要调用哪些执行器"
4. 胞式应该是原子的、可复用的
5. 行技通过编排胞式形成完整能力
```

## 6. 能量计量规则（炽心核）

```yaml
# 能量计量配置
energy_config:
  # 基础消耗
  base_costs:
    file_io: 0.5
    sql_query: 1
    http_call: 2
    llm_call: 5
    
  # 倍率
  multipliers:
    per_mb: 0.5
    per_1k_rows: 0.1
    per_column: 0.1
    
  # 限制
  limits:
    max_per_cell: 20
    max_per_xingji: 50
    daily_quota: 1000
```
