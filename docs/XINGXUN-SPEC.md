# 星询 (XīngXún) — 星图语义探索协议

> 版本: 0.1.0 | 状态: 设计稿
> 
> **定位**：Agent 与星图元系统之间的多轮语义查询协议  
> **核心理念**：不是一次拉取，而是连续探索；不是固定查询，而是动态演化语义

---

## 1. 设计原则

### 1.1 为什么不能用 SQL / GraphQL？

| 传统查询 | 星询 |
|---------|------|
| 无状态，每次独立 | **有状态**，每次查询继承上下文 |
| 查询者必须知道 schema | **schema 是被探索的对象** |
| 返回数据行 | 返回**知识片段 + 导航建议** |
| 固定语义 | **语义随探索动态演化** |
| 查完即结束 | **查询产出假设，假设驱动下一次查询** |

### 1.2 核心设计原则

1. **会话式** — 查询在 Session 内积累上下文，后续查询自动继承前文
2. **渐进式** — 从粗到细，先概览再深入，agent 控制探索粒度
3. **可验证** — 每个返回结果都可以被确认或否定，形成知识闭环
4. **多模态** — 同一个查询框架可以查数据结构、业务语义、规则约束、完备性
5. **自描述** — 返回结果中包含"还能问什么"的导航提示

---

## 2. 会话模型

### 2.1 Session 生命周期

```
create_session(goal?)
    │
    ▼
┌─────────────────────────────────────────┐
│  Session (有状态，持续积累)              │
│                                         │
│  focus: [当前关注的概念/对象]            │
│  scope: 当前领域范围                    │
│  discoveries: [已确认的知识]            │
│  hypotheses: [待验证的假设]             │
│  trail: [探索路径历史]                  │
│                                         │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  │
│  │ Q1  │→│ Q2  │→│ Q3  │→│ Q4  │  │
│  └─────┘  └─────┘  └─────┘  └─────┘  │
│    ↓         ↓        ↓        ↓      │
│   发现A    验证A    发现B   组装上下文 │
│            ✓确认    假设C             │
└─────────────────────────────────────────┘
    │
    ▼
close_session → 知识沉淀到星图
```

### 2.2 Session 数据结构

```yaml
Session:
  id: "xs_a1b2c3"
  goal: "分析Q4销售下降原因"          # 可选，声明探索目标
  created_at: "2026-02-07T10:00:00Z"
  
  # 动态累积的上下文
  context:
    focus: ["销售", "客户"]            # 当前聚焦的概念
    scope: "电商业务"                  # 当前领域范围
    depth: "conceptual"                # 当前探索深度
    
  # 探索产出
  discoveries:                         # 已确认的事实
    - id: "d_001"
      fact: "销售表通过 customer_id 关联客户表"
      confidence: 1.0
      source: "schema_inspection"
      
  hypotheses:                          # 待验证的假设
    - id: "h_001"
      claim: "Q4下降可能与客户流失相关"
      status: "unverified"
      suggested_verification: "check_churn_rate_trend"
      
  trail:                               # 探索路径
    - { query: "explore('销售')", result_summary: "发现3个相关数据源" }
    - { query: "relate('销售', '客户')", result_summary: "找到1条关联路径" }
```

---

## 3. 查询算子 (Operators)

星询定义 6 类算子，每类解决一个认知需求：

### 3.1 探索算子 (Explore) — "那里有什么？"

```yaml
# 开放式探索：从一个概念出发，看周围有什么
explore:
  target: "销售"                    # 概念/关键词/对象名
  mode: "概览"                      # 概览 | 详细 | 结构
  radius: 2                         # 探索半径（关系跳数）
  
# 返回：
→ nodes:                            # 发现的节点
    - { type: "object", name: "sales_2024", relevance: 0.95 }
    - { type: "object", name: "customer", relevance: 0.80 }
    - { type: "concept", name: "退货", relevance: 0.60 }
  edges:                            # 发现的关系
    - { from: "sales_2024", to: "customer", type: "FK", via: "customer_id" }
  suggestions:                      # 后续可探索的方向
    - { action: "focus('sales_2024')", reason: "查看销售表的详细结构" }
    - { action: "relate('销售', '退货')", reason: "退货可能影响销售趋势" }
    - { action: "gaps('销售分析')", reason: "检查分析所需数据是否完整" }
```

```yaml
# 聚焦：深入一个特定对象/概念
focus:
  target: "sales_2024"
  aspect: "structure"               # structure | semantics | quality | usage
  
# 返回：
→ object:
    name: "sales_2024"
    display_name: "2024年销售明细"
    type: "csvFile"
    row_count: 150000
    status: "published"
  properties:                       # 只返回关键属性摘要
    total: 22
    key_fields:
      - { name: "order_id", semantic: "primaryKey", quality: "完整" }
      - { name: "amount", semantic: "amount", unit: "元", quality: "完整" }
      - { name: "customer_id", semantic: "foreignKey", links_to: "customer.id" }
      - { name: "order_date", semantic: "timestamp", range: "2024-01-01 ~ 2024-12-31" }
    expandable: true                # 表示还有更多属性可以展开
  suggestions:
    - { action: "expand('sales_2024', 'properties')", reason: "查看全部22个字段" }
    - { action: "trace('sales_2024.customer_id → customer')", reason: "跟踪客户关联" }
```

### 3.2 关联算子 (Relate) — "它们之间有什么联系？"

```yaml
# 查找两个概念/对象之间的关联路径
relate:
  from: "sales_2024"
  to: "product_catalog"
  max_hops: 3                       # 最大跳数
  include_indirect: true            # 是否包含间接关系
  
# 返回：
→ paths:
    - path: ["sales_2024.product_id", "→ FK →", "product_catalog.id"]
      type: "direct"
      confidence: 1.0
      verified: true
    - path: ["sales_2024.category", "→ 语义相似 →", "product_catalog.category_name"]
      type: "semantic_match"
      confidence: 0.72
      verified: false               # 未经验证的推断
  no_path:                          # 找不到路径时的说明
    - "sales_2024 与 logistics_data 之间没有直接关系键"
  hypotheses:                       # 基于路径发现产生的假设
    - id: "h_002"
      claim: "sales.category 可能就是 product.category_name 的简写"
      verification: "verify({ assertion: 'sales.category 值域 ⊂ product.category_name 值域' })"
```

### 3.3 语义算子 (Semant) — "这个东西意味着什么？"

```yaml
# 查询业务含义
define:
  term: "客户等级"
  context: "销售分析"                # 可选的语境限定
  
# 返回：
→ definition:
    term: "客户等级"
    meaning: "基于年度消费总额对客户进行分层的分类体系"
    source: "ai_inferred"           # 来源标记
    confidence: 0.75
  realizations:                     # 在数据中的具体实现
    - { object: "customer", field: "level", values: ["A","B","C","D"] }
    - { object: "crm_contacts", field: "tier", values: ["VIP","Gold","Silver","Bronze"] }
  rules:                            # 相关规则
    - { rule: "VIP = 年消费 > 10万", source: "unverified", confidence: 0.60 }
  related_terms:                    # 相关术语
    - { term: "客户价值", relation: "broader" }
    - { term: "RFM模型", relation: "methodology" }
  note: "⚠ 此定义由 AI 推断，尚未经人工确认"
```

```yaml
# 查询指标定义
measure:
  metric: "客单价"
  
# 返回：
→ metric:
    name: "客单价"
    formula: "SUM(amount) / COUNT(DISTINCT customer_id)"
    unit: "元"
    granularity: ["日", "月", "季度"]
    dimensions: ["地区", "客户等级", "产品类别"]
  data_sources:
    required: ["sales_2024.amount", "sales_2024.customer_id"]
    available: true                  # 数据是否可用
  caveats:
    - "退货订单是否需要排除？当前公式未区分"
    - "同一客户多次下单算一个还是多个？"
```

### 3.4 验证算子 (Verify) — "这个说法对吗？"

```yaml
# 验证一个断言
verify:
  assertion: "sales_2024.customer_id 的值域完全包含在 customer.id 中"
  method: "data_check"              # schema_check | data_check | rule_check
  
# 返回：
→ result:
    assertion: "sales_2024.customer_id ⊆ customer.id"
    verdict: "partial"              # true | false | partial | unknown
    evidence:
      total_values: 8500
      matched: 8200
      unmatched: 300
      match_rate: 0.965
    interpretation: "96.5% 匹配，有 300 个 customer_id 在客户表中找不到"
    impact: "关联分析时会丢失约 3.5% 的订单数据"
    suggestions:
      - "verify({ assertion: '缺失的300个ID是否为已删除客户' })"
      - "这300条记录可能是测试数据或数据质量问题"
```

```yaml
# 验证一条关联路径
validate_path:
  path: ["sales.customer_id", "→", "customer.id", "→", "customer.region"]
  purpose: "按地区分析销售额"
  
# 返回：
→ result:
    valid: true
    join_type: "LEFT JOIN"           # 建议的连接方式
    data_loss_risk: 0.035            # 预计数据丢失比例
    cardinality: "N:1:1"            # 每段的基数
    warnings:
      - "customer.region 有 12% 的空值"
    executable_sql: |                # 可执行的 SQL（如果适用）
      SELECT c.region, SUM(s.amount) as total
      FROM sales_2024 s
      LEFT JOIN customer c ON s.customer_id = c.id
      GROUP BY c.region
```

### 3.5 完备性算子 (Coverage) — "我还缺什么？"

```yaml
# 检查知识完备性
gaps:
  goal: "分析Q4销售下降原因"
  current_knowledge:                 # 可引用 session 中已有的 discoveries
    - "d_001"
    - "d_002"
    
# 返回：
→ coverage:
    overall: 0.65                    # 总体覆盖度
    dimensions:
      - { name: "交易数据", coverage: 0.95, status: "充分" }
      - { name: "客户画像", coverage: 0.70, status: "部分", missing: ["客户满意度", "客户来源渠道"] }
      - { name: "产品数据", coverage: 0.85, status: "基本充分" }
      - { name: "外部因素", coverage: 0.10, status: "严重不足", missing: ["竞品动态", "市场趋势", "季节系数"] }
      - { name: "运营数据", coverage: 0.30, status: "不足", missing: ["营销活动", "促销力度"] }
    critical_gaps:
      - { gap: "缺少营销活动数据", impact: "无法区分'自然下降'和'促销减少导致的下降'" }
      - { gap: "缺少去年同期对比", impact: "无法排除季节性因素" }
    recommendations:
      - { action: "import('营销活动记录')", priority: "high" }
      - { action: "derive('同比增长率')", priority: "high", method: "从现有销售数据可计算" }
```

### 3.6 组装算子 (Assemble) — "给我准备好上下文"

```yaml
# 为特定任务组装知识上下文
assemble:
  purpose: "用 SQL 分析Q4各地区销售变化"
  format: "agent_context"            # agent_context | sql_ready | report_ready
  max_tokens: 2000                   # 上下文预算
  
# 返回：
→ context:
    summary: |
      你有以下数据可用于分析Q4各地区销售变化：
      
      【核心表】sales_2024（15万行），包含 order_id, amount, customer_id, order_date, region 等22个字段
      【关联表】customer（8500行），通过 customer_id 关联，包含客户等级、注册时间等
      【关联表】product_catalog（1200行），通过 product_id 关联
      
      【可用指标】销售额=SUM(amount), 客单价=AVG(amount), 订单量=COUNT(order_id)
      【可用维度】地区(region, 15个值), 月份(order_date), 客户等级(level, 4个值)
      
      【注意事项】
      - customer_id 有3.5%无法关联到客户表
      - customer.region 有12%空值
      - 没有营销活动数据，无法分析促销影响
      
    schema_details:                  # 精选的 schema（不是全量）
      sales_2024:
        key_columns: [order_id, amount, customer_id, order_date, region, product_id]
        row_count: 150000
        date_range: "2024-01-01 ~ 2024-12-31"
      customer:
        key_columns: [id, level, region, created_at]
        row_count: 8500
    join_map:                        # 预组装的关联路径
      - "sales_2024.customer_id = customer.id (LEFT JOIN, 96.5%匹配)"
      - "sales_2024.product_id = product_catalog.id (INNER JOIN, 99.8%匹配)"
    verified_facts:                  # 本次 session 中已验证的事实
      - "Q4 = 10月-12月"
      - "客户等级分 A/B/C/D 四级"
```

---

## 4. 查询语法

### 4.1 简洁语法（MCP 工具参数）

每个算子映射为一个 MCP 工具调用：

```yaml
tools:
  # 会话管理
  - xingxun_session:       { action: "create|close", goal?: string }
  
  # 6 类算子
  - xingxun_explore:       { target: string, mode?: string, radius?: int }
  - xingxun_focus:         { target: string, aspect?: string }
  - xingxun_relate:        { from: string, to: string, max_hops?: int }
  - xingxun_define:        { term: string, context?: string }
  - xingxun_measure:       { metric: string }
  - xingxun_verify:        { assertion: string, method?: string }
  - xingxun_validate_path: { path: string[], purpose?: string }
  - xingxun_gaps:          { goal: string }
  - xingxun_assemble:      { purpose: string, format?: string, max_tokens?: int }
  
  # 导航快捷方式
  - xingxun_expand:        { node: string, aspect: string }   # 展开某个节点的详情
  - xingxun_back:          {}                                  # 回到上一个焦点
  - xingxun_pivot:         { from: string, direction: string } # 转向新方向
```

### 4.2 组合语法（支持管道式调用）

Agent 可以在单次请求中组合多个算子：

```yaml
# 管道式：前一个的输出作为后一个的输入
xingxun_pipe:
  steps:
    - explore: { target: "销售" }
    - focus: { target: "$result.nodes[0].name" }   # 引用上一步结果
    - gaps: { goal: "趋势分析" }
```

```yaml
# 条件式：根据结果决定下一步
xingxun_branch:
  query: { verify: { assertion: "sales.customer_id ⊆ customer.id" } }
  if_true: { assemble: { purpose: "安全执行关联查询" } }
  if_false: { gaps: { goal: "修复数据关联" } }
```

---

## 5. 返回结构规范

### 5.1 统一返回信封

所有算子返回统一结构：

```yaml
XingXunResponse:
  # 元信息
  meta:
    session_id: "xs_a1b2c3"
    query_id: "xq_d4e5f6"
    operator: "explore"
    elapsed_ms: 45
    
  # 主体结果
  result: { ... }                    # 算子特定的结果
  
  # 知识产出（自动追加到 session）
  discoveries: []                    # 新确认的事实
  hypotheses: []                     # 新产生的假设
  
  # 导航建议（核心！引导 agent 下一步）
  suggestions:
    - action: "focus('customer')"
      reason: "客户表与当前分析目标高度相关"
      priority: "high"
    - action: "verify({ assertion: '...' })"
      reason: "发现一个未验证的关联，建议确认"
      priority: "medium"
      
  # 上下文变化（session 状态更新）
  context_update:
    focus_added: ["sales_2024"]
    focus_removed: []
    scope_narrowed: false
    
  # 溯源与可信度
  provenance:
    sources: ["schema_inspection", "ai_inference"]
    overall_confidence: 0.85
    unverified_count: 2              # 返回中有几项未经验证
```

### 5.2 三种详细程度

Agent 可以控制返回的详细程度：

```yaml
# 简洁模式：适合快速扫描
xingxun_explore:
  target: "销售"
  verbosity: "brief"                 # brief | standard | full

# brief 返回：
→ "发现 3 个相关对象: sales_2024(15万行), customer(8500行), product(1200行)。
   建议: focus('sales_2024') 或 gaps('销售分析')"

# standard 返回：结构化 YAML（默认）

# full 返回：包含所有字段详情、样本值、统计信息
```

---

## 6. 语义演化机制

### 6.1 查询意图的动态修正

Agent 可以在探索过程中修正自己的理解：

```yaml
# 第1步：Agent 以为 "level" 是"级别"
xingxun_define:
  term: "level"
  context: "customer表"

# 返回告诉 Agent："level" 在此处表示"客户等级"，值域为 A/B/C/D

# 第2步：Agent 修正理解，重新查询
xingxun_explore:
  target: "客户等级"                  # 用修正后的语义重新探索
  
# Session 自动记录这次语义演化：
# trail: [
#   { intent: "level是什么", resolution: "客户等级(A/B/C/D)" },
#   { intent: "围绕客户等级探索", resolution: "..." }
# ]
```

### 6.2 假设驱动的探索循环

```
Agent 提出假设 → verify → 确认/否定 → 调整方向 → 新假设 → ...

例:
  H1: "Q4下降是因为大客户流失"
    → verify: 检查大客户(level=A)的Q4订单量
    → 结果: 大客户订单量持平，否定 H1
    
  H2: "Q4下降是因为中小客户减少"
    → verify: 检查 level=C,D 的Q4订单量
    → 结果: 确实下降30%，初步确认 H2
    
  H3: "中小客户减少是因为没有促销活动"
    → gaps: 缺少营销活动数据，无法验证
    → 标记为 "blocked"，等待数据补充
```

### 6.3 Session 间的知识传递

```yaml
# 一个 Session 的 discoveries 可以沉淀为星图的永久知识
xingxun_session:
  action: "close"
  persist_discoveries: true          # 将 discoveries 写入星图
  persist_hypotheses: false          # 假设不自动持久化
  
# 下次新 Session 可以引用之前的知识
xingxun_session:
  action: "create"
  goal: "深入分析中小客户流失"
  inherit_from: "xs_a1b2c3"         # 继承上一个 session 的 discoveries
```

---

## 7. 多模态查询矩阵

同一个问题，不同模态的表达：

```
Agent 想知道: "客户和销售的关系是什么？"

模态 1 — 结构模态 (schema)
  → relate: { from: "customer", to: "sales_2024" }
  ← "customer.id → sales_2024.customer_id (1:N, FK)"

模态 2 — 语义模态 (meaning)
  → define: { term: "客户-销售关系" }
  ← "一个客户可以有多笔销售订单，通过 customer_id 关联"

模态 3 — 数据模态 (evidence)  
  → verify: { assertion: "每个客户平均有多少笔订单" }
  ← "平均 17.6 笔/客户，中位数 8 笔，最大 523 笔"

模态 4 — 质量模态 (quality)
  → focus: { target: "customer↔sales关联", aspect: "quality" }
  ← "96.5% 可成功关联，3.5% 缺失，空值影响地区分析"

模态 5 — 操作模态 (actionable)
  → assemble: { purpose: "按客户分析销售" }
  ← "LEFT JOIN customer ON ... , 注意 region 有12%空值"
```

---

## 8. 错误处理与边界

### 8.1 知识边界声明

```yaml
# 当星图无法回答时，明确声明边界
xingxun_define:
  term: "客户生命周期"

# 如果星图中没有这个概念：
→ result:
    found: false
    boundary: "星图中没有'客户生命周期'的定义"
    nearest:
      - { term: "客户等级", similarity: 0.6, note: "相关但不同" }
      - { term: "客户创建时间", similarity: 0.4 }
    suggestion: "可以通过 customer.created_at 和购买记录推导客户生命阶段"
    register_prompt: "是否要将'客户生命周期'注册为新概念？"
```

### 8.2 置信度分级

```yaml
confidence_levels:
  verified:    1.0    # 经人工确认或数据验证
  high:        0.8+   # AI 高置信度推断 + schema 支撑
  medium:      0.5+   # AI 推断，有部分证据
  low:         0.3+   # AI 猜测，证据不足
  speculative: <0.3   # 纯推测
  
# 每个返回的知识片段都带置信度标记
# Agent 可以设置信任阈值：
xingxun_session:
  action: "create"
  trust_threshold: 0.7              # 低于此值的知识标记为 ⚠
```

---

## 9. 完整交互示例

```
Agent 任务: "帮我理解这个数据库，准备分析Q4销售"

── Step 1: 开始 ──────────────────────────────────

→ xingxun_session: { action: "create", goal: "理解数据全貌，准备Q4销售分析" }
← session_id: "xs_001"
  initial_overview:
    total_objects: 5
    domains: ["销售", "客户", "产品"]
    suggestion: "explore('销售') 开始探索核心数据"

── Step 2: 探索销售域 ────────────────────────────

→ xingxun_explore: { target: "销售", mode: "概览" }
← nodes: [sales_2024, sales_2023, returns_2024]
  edges: [sales→customer(FK), sales→product(FK)]
  suggestions:
    - focus('sales_2024') — "最新且数据量最大"
    - relate('sales_2024', 'sales_2023') — "做同比需要"

── Step 3: 聚焦核心表 ────────────────────────────

→ xingxun_focus: { target: "sales_2024", aspect: "structure" }
← 22个字段，15万行，关键字段: order_id, amount, customer_id, order_date, region
  quality: { completeness: 0.98, freshness: "2天前" }
  suggestions:
    - relate('sales_2024', 'customer') — "分析客户维度"
    - measure('销售额') — "了解核心指标定义"

── Step 4: 理解核心指标 ──────────────────────────

→ xingxun_measure: { metric: "销售额" }
← formula: SUM(amount), 可按 region/month/level 切分
  caveat: "退货数据在 returns_2024 中，当前公式未扣除"

── Step 5: 验证关联路径 ──────────────────────────

→ xingxun_validate_path:
    path: ["sales_2024.customer_id", "customer.id", "customer.level"]
    purpose: "按客户等级分析销售"
← valid: true, match_rate: 0.965, warnings: ["3.5%无法关联"]
  discovery → "d_003: 销售-客户关联路径有效但有3.5%数据缺口"

── Step 6: 检查完备性 ────────────────────────────

→ xingxun_gaps: { goal: "分析Q4销售下降原因" }
← coverage: 0.65
  critical_gaps: ["营销活动数据", "去年同期对比方法"]
  derivable: "同比增长率可从 sales_2023 + sales_2024 计算"

── Step 7: 组装最终上下文 ────────────────────────

→ xingxun_assemble: { purpose: "SQL分析Q4各地区销售变化", max_tokens: 2000 }
← 精炼的上下文，包含:
  - 3张核心表的精选 schema
  - 预验证的 JOIN 路径
  - 可用指标和维度
  - 数据质量警告
  - 知识缺口提示

── Step 8: 关闭并沉淀 ────────────────────────────

→ xingxun_session: { action: "close", persist_discoveries: true }
← 5 条 discoveries 沉淀到星图
  2 条 hypotheses 待后续验证
```

---

## 10. 与现有 MCP 工具的兼容

星询不替代现有的 `xingtu_*` 工具，而是在其上层：

```
┌─────────────────────────────────────────────┐
│   星询 (XīngXún) — 语义探索层              │
│   xingxun_explore / relate / verify / ...   │
│   有状态、多轮、可验证                      │
└──────────────────┬──────────────────────────┘
                   │ 内部调用
┌──────────────────▼──────────────────────────┐
│   星图 CRUD — 数据操作层                    │
│   xingtu_list_objects / get_properties /... │
│   无状态、单次、原子操作                    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│   SQLite — 存储层                           │
└─────────────────────────────────────────────┘
```

Agent 可以混用两层：
- **星询** 用于探索和理解
- **星图 CRUD** 用于写入和修改数据

---

*创建时间: 2026-02-07*  
*Owner: 星空座*
