# 星询符号语义 (XīngXún Symbolic)

> v0.2 | 替代 v0.1 的理想化协议设计
>
> **一句话**：用符号指代知识，用表达式组合语义，表达式解析为算子网，算子网对星图执行。

---

## 0. 为什么用符号

Agent 每次调用都要拼 JSON、传参数名，太重。
符号语义的目标：**Agent 用一行表达式就能读、写、验、推**。

```
# 读 — 这个客户表有什么？
@customer.*

# 写 — 我发现了一个规则
@customer.level := {年消费 > 10万: "VIP", > 5万: "A", > 1万: "B", _: "C"}

# 验 — 这个关联对不对？
@order.customer_id ?= @customer.id

# 推 — 基于已知推导
@q4_revenue := @order[date in Q4].amount | SUM
```

表达式不是给人看的，是给 agent 和解析器看的。
解析器把表达式变成**算子网**（一个 DAG），对星图执行。

---

## 1. 符号体系

### 1.1 四种基本符号

```
符号          含义              示例
──────────────────────────────────────────────────
@name         实体引用          @customer  @order  @product
@a.b          属性访问          @customer.level  @order.amount
@a → @b       关系路径          @order → @customer
#tag          语义标签          #度量  #维度  #时间  #主键
```

- `@` 开头：指向星图中的一个节点（对象、概念、属性）
- 如果节点不存在，写入操作会**自动创建**（星图在 agent 使用中生长）
- `.` 访问属性，`→` 跟踪关系

### 1.2 操作符

```
操作符        语义              类别
──────────────────────────────────────────────────
?             查询/探索         读
?=            验证相等/匹配     验
?~            模糊匹配/相关     验
:=            定义/赋值         写
+=            追加知识          写
-=            撤回知识          写
~>            推导/转换         推
|             管道/链式         组合
[]            过滤/条件         组合
{}            结构/映射         组合
!             断言（必须为真）  验
!!            强制更新          写
```

### 1.3 语法骨架

```
表达式 ::= 符号 操作符 符号        -- 二元操作
         | 符号 操作符              -- 一元查询
         | 符号 "[" 条件 "]"       -- 带过滤
         | 表达式 "|" 表达式       -- 管道
         | 符号 ":=" 值            -- 定义
```

---

## 2. 读：从星图获取知识

```python
# 列出所有已知实体
@*

# 查看一个实体的概况
@customer?

# 查看一个属性的详情
@customer.level?

# 探索周围的关系
@customer →?

# 带条件过滤
@customer[status = "published"]?

# 沿关系路径查询
@order → @customer → @customer.level?

# 聚合
@order.amount | SUM
@order[date in "2024-Q4"].amount | SUM | AS @q4_revenue

# 分组
@order.amount | BY @customer.level | SUM
```

### 读操作的算子网分解

```
表达式: @order[date in Q4] → @customer.level | BY level | COUNT

解析为算子网（DAG）:

  [Resolve @order]          -- 解析符号，定位 meta_object
       │
  [Filter date∈Q4]          -- 条件过滤算子
       │
  [Traverse →@customer]     -- 关系遍历算子（走 FK）
       │
  [Access .level]            -- 属性访问算子
       │
  [GroupBy level]            -- 分组算子
       │
  [Aggregate COUNT]          -- 聚合算子
       │
     结果
```

每个方块就是算子网中的一个节点。数据从上往下流。

---

## 3. 写：向星图注入知识

Agent 在使用中不断发现新知识，直接写回星图：

```python
# 注册新概念（如果不存在就创建）
@客户生命周期 := concept {
  stages: [潜在, 活跃, 沉默, 流失, 回归],
  derive_from: @customer.created_at & @order.date
}

# 定义一个指标
@客单价 := @order.amount | SUM / @order.customer_id | DISTINCT | COUNT

# 定义业务规则
@customer.level := {
  @customer.annual_amount > 100000 : "VIP",
  @customer.annual_amount > 50000  : "A",
  @customer.annual_amount > 10000  : "B",
  _                                : "C"
}

# 追加关系
@order.product_id += FK → @product.id

# 追加语义标注
@order.amount += #度量 #金额 #元

# 记录发现
@order.return_rate += note("退货率Q4偏高，可能与大促有关")

# 修正错误知识
@customer.region !! {
  "华东" → "East China",   -- 修正映射
  confidence: 0.9,
  reason: "统一为英文编码"
}

# 撤回不准确的知识
@customer.age -= rule("年龄 > 150 视为脏数据")  -- 这条规则被发现不合理
```

### 写操作的算子网

```
表达式: @客单价 := @order.amount | SUM / @order.customer_id | DISTINCT | COUNT

解析为:

  [Resolve @order.amount]    [Resolve @order.customer_id]
       │                            │
  [Aggregate SUM]           [Aggregate DISTINCT]
       │                            │
       │                    [Aggregate COUNT]
       │                            │
       └──────────┬─────────────────┘
            [Divide /]
                 │
         [Define @客单价]        -- 写入星图，创建 metric_def
                 │
            沉淀到星图
```

---

## 4. 验：校验知识的正确性

```python
# 验证 FK 完整性
@order.customer_id ?= @customer.id
# → { match: 96.5%, unmatched: 300, verdict: "partial" }

# 验证值域包含
@order.region ?⊆ @region_master.code
# → { contained: true }

# 验证公式一致性
@客单价 ?= @order.amount | SUM / @order | DISTINCT customer_id | COUNT
# → { consistent: true, note: "与已有定义一致" }

# 模糊验证（语义相关性）
@customer.level ?~ @customer.tier
# → { similar: true, confidence: 0.82, mapping: {"VIP"↔"Premium", "A"↔"Gold", ...} }

# 断言（必须为真，否则报错）
@order.amount ! > 0
# → { violations: 23, sample: [...] }

# 路径可达性验证
@order →? @product →? @supplier
# → { reachable: true, path: "order.product_id → product.id → product.supplier_id → supplier.id" }
```

### 验证的算子网

```
表达式: @order.customer_id ?= @customer.id

解析为:

  [Resolve @order.customer_id]    [Resolve @customer.id]
            │                              │
       [Distinct values]            [Distinct values]
            │                              │
            └────────────┬─────────────────┘
                  [SetCompare ?=]
                         │
                   验证报告
            { match: 96.5%, unmatched: 300 }
```

---

## 5. 推：基于已知推导新知

```python
# 推导新属性
@customer.lifetime_value ~> @order[customer_id = @customer.id].amount | SUM

# 推导关系（从数据模式推断）
@order.product_id ~> FK? @product.id
# 引擎检查值域重叠度，自动判断是否是FK

# 链式推导
@月销售趋势 ~> @order | BY month(date) | SUM amount | TREND
# 引擎执行聚合 + 趋势计算

# 因果推导（标记为假设）
@customer.churn ~> CORRELATE(@customer.satisfaction, @customer.last_order_days)
# → hypothesis { correlation: -0.67, confidence: 0.72, status: "unverified" }
```

---

## 6. 算子网 (Operator Net)

### 6.1 算子类型

```
类型              符号触发        作用
──────────────────────────────────────────────────
Resolve           @name          符号 → 星图节点
Access            .prop          节点 → 属性值
Traverse          →              关系 → 目标节点
Filter            [cond]         集合 → 子集
Aggregate         SUM/COUNT/...  集合 → 标量
GroupBy           BY field       集合 → 分组集合
Define            :=             值 → 星图写入
Append            +=             值 → 星图追加
Retract           -=             值 → 星图删除
Verify            ?= / ?~ / !   两值 → 验证报告
Derive            ~>             已知 → 推导新知
Pipe              |              算子 → 算子 (串联)
Fork              &              算子 → 算子 (并行)
Join              ⊕              多流 → 合并
```

### 6.2 算子网是 DAG

每条星询表达式解析成一个 **有向无环图**：
- **节点**是算子
- **边**是数据流
- 叶子节点是 `Resolve`（从星图取数据）或字面量
- 根节点是最终操作（返回结果 / 写入星图 / 验证报告）

```
复合表达式:
  @order[date in Q4].amount | BY (@order → @customer).level | SUM

算子网:

    Resolve(@order)
         │
    Filter(date∈Q4)──────────────Resolve(@order)
         │                            │
    Access(.amount)              Traverse(→@customer)
         │                            │
         │                       Access(.level)
         │                            │
         └───────────┬────────────────┘
               GroupBy(level)
                     │
               Aggregate(SUM)
                     │
                   结果
```

### 6.3 算子网的执行策略

```
1. 惰性求值：只解析需要的节点，不提前加载全部数据
2. 缓存：同一 session 内，Resolve 结果缓存，不重复查 DB
3. 增量：写入操作立即生效，后续读操作自动读到新值
4. 失败传播：任何算子失败，向下游传播 Error（不中断整个网）
5. 置信度传播：每个算子输出带 confidence，沿管道衰减
```

---

## 7. Agent 实际使用方式

### 7.1 MCP 工具接口

Agent 通过一个统一工具提交星询表达式：

```yaml
tool:
  name: xingxun
  input:
    expr: string        # 星询表达式
    session: string?    # 可选 session id（延续上下文）
  output:
    result: any         # 执行结果
    side_effects: []    # 对星图的写入
    suggestions: []     # 下一步建议（可选）
    confidence: float   # 结果置信度
```

### 7.2 真实 Agent 调用流程

```python
# Agent 第一次接触这个数据环境
xingxun(expr="@*")
# → ["order", "customer", "product", "returns", "region_master"]
#   suggestions: ["@order? — 最大的表，15万行"]

# Agent 了解核心表
xingxun(expr="@order?")
# → { fields: 22, rows: 150000, key: "order_id", 
#     relations: ["→customer(FK)", "→product(FK)"],
#     tags: [#交易, #核心] }

# Agent 验证关联
xingxun(expr="@order.customer_id ?= @customer.id")
# → { match: 96.5%, gap: 300 }

# Agent 定义发现的规则
xingxun(expr='@customer.level := {annual > 100000: "VIP", > 50000: "A", > 10000: "B", _: "C"}')
# → { defined: "@customer.level", stored: true }

# Agent 推导指标
xingxun(expr="@q4_revenue := @order[date in Q4].amount | SUM")
# → { value: 12500000, stored_as: "metric:q4_revenue" }

# Agent 做分析
xingxun(expr="@order[date in Q4].amount | BY (@order → @customer).level | SUM")
# → { VIP: 5000000, A: 4000000, B: 2500000, C: 1000000 }

# Agent 发现问题，记录假设
xingxun(expr='@order += hypothesis("Q4 C类客户下降30%，疑似促销减少")')
# → { recorded: true, id: "h_001" }
```

### 7.3 知识自动生长

每次 Agent 使用星询，星图都可能生长：

```
Agent A 今天: @客单价 := @order.amount | SUM / @order.customer_id | DISTINCT | COUNT
  → 星图新增 metric_def: 客单价

Agent B 明天: @客单价?
  → 直接获取定义，不用重新推导

Agent B: @客单价 BY @customer.level
  → 直接使用已有定义做分组计算

Agent C 下周: @客单价 !! @order[status != "退货"].amount | SUM / ...
  → 修正了客单价定义（排除退货），星图更新，所有 agent 受益
```

这就是**集体知识的增量积累**——每个 agent 的使用都在强化星图。

---

## 8. 符号解析规则

### 8.1 符号解析优先级

当 Agent 写 `@customer` 时，解析器按以下顺序查找：

```
1. Session 内定义（本次对话中 := 定义的）
2. 概念层（concepts 表，如果存在）
3. 对象层（meta_objects 表，按 name 匹配）
4. 属性层（meta_properties 表，按 display_name 匹配）
5. 模糊匹配（用编辑距离/语义相似度）
6. 未找到 → 如果是写操作，自动创建；如果是读操作，返回 not_found + 建议
```

### 8.2 歧义处理

```python
# 如果 "level" 在多个表中都有
@level?
# → ambiguous: ["@customer.level", "@product.level"]
#   需要限定: @customer.level? 或 @product.level?

# 用上下文自动消歧
# 如果 session 当前 focus 是 customer，则 @level 自动解析为 @customer.level
```

### 8.3 类型推断

```
@order.amount | SUM          -- amount 是数值 → SUM 合法
@order.amount | DISTINCT     -- amount 是数值 → DISTINCT 合法
@order.status | SUM          -- status 是字符串 → SUM 非法 → 报类型错误
@order.date | RANGE          -- date 是时间 → RANGE 返回 [min, max]
```

---

## 9. 最小实现集

不需要一步实现全部。最小可用版本只需要：

### Phase 0: 符号读取（替代 get_world_model 全量转储）

```
@*                     → list_objects
@name?                 → get_object + get_properties
@name.prop?            → get single property
@a → @b                → get_relations
```

### Phase 1: 过滤与聚合

```
@name[condition]       → filtered query
@name.prop | SUM/COUNT → aggregation
@name.prop | BY field  → group by
```

### Phase 2: 写入与学习

```
@name := definition    → create concept/metric
@name.prop += tag      → annotate
@a.x ?= @b.y          → verify FK integrity
```

### Phase 3: 推导与假设

```
@metric ~> formula     → derive with computation
+= hypothesis(...)    → record hypothesis
!! correction          → force update
```

---

## 10. 与前一版的对比

| v0.1 (理想化协议) | v0.2 (符号语义) |
|---|---|
| 13 个 MCP 工具 | **1 个工具** (`xingxun(expr=...)`) |
| 每次调用传大段 YAML | 一行符号表达式 |
| 固定的查询模式 | 自由组合的算子 |
| 读写分离 | 读写验推统一语法 |
| Session 管理复杂 | Session 可选，符号自带上下文 |
| Agent 必须学习协议 | Agent 像写公式一样自然 |

核心变化：**从"Agent 调用 API"变成"Agent 用公式与知识交互"**。

---

*v0.2 | 2026-02-07 | 星空座*
