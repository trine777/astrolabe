# Box 模型设计讨论 Room ⚠️ 已回滚，留作历史记录

> **回滚日期: 2026-04-21**
> **回滚原因**: 架构职责搞错了。向量化 951 doc 进星图是记忆系统的用法，不是星图的用法。
> 正确分工：星图 = 地图 + 元数据；玄武 = 数据存储；记忆系统 = 向量召回。
>
> 讨论日期: 2026-04-21
> 参与者: Trine (决策), Claude (主笔)
> 目的: Agent 导航式知识访问 — 从盲搜 951 文档 → 分层定位
> 基础数据: 951 文档 × 1024 维 BGE-M3 向量 × 6 collection (~/.xingtu-local/)

---

## 已决议（FIXED）

| 编号 | 决议 | 备注 |
|------|------|------|
| F-1 | **层级 3 层** | World → Region → Area → Docs |
| F-2 | **嵌入 = BGE-M3 (1024 维)** | 已有，不重算 |
| F-3 | **数据根在 `~/.xingtu-local/data/`** | 不动 Docker 数据 |

---

## 待决议维度（按影响大小排序）

### D-1. 层级分支因子 — 每层几个 box？

3 层 × 951 文档，关键是每层分多少。

| 选项 | World | Region | Area | 叶子 doc/box | 适合场景 |
|------|-------|--------|------|--------------|----------|
| A. **宽扁** | 1 | 15 | 每 region 4 个 = 60 | ~16 | 浅导航，快定位 |
| B. **方正** | 1 | 10 | 每 region 6 个 = 60 | ~16 | 平衡 |
| C. **深窄** | 1 | 6 | 每 region 10 个 = 60 | ~16 | 每层选择少，决策路径长 |
| D. **自适应** | 1 | HDBSCAN 自动 | 自动 | 变化 | 灵活但不可控 |

**Claude 倾向**: **B. 方正 (1→10→60)**，Region 层对齐人的短期记忆（7±2），Area 层有具体感。

**你选**: ___

---

### D-2. 聚类算法

| 选项 | 优点 | 缺点 | 依赖 |
|------|------|------|------|
| A. **KMeans (固定 k)** | 可复现、可控、无新依赖 | 需手动调 k、球形簇假设 | 已有 sklearn |
| B. **MiniBatchKMeans** | KMeans + 更快 + 省内存 | 同上 | 已有 sklearn |
| C. **HDBSCAN** | 自动簇数、抗噪 | 新依赖、簇数不可控 | 需装 `hdbscan` |
| D. **层级聚类 (Ward)** | 天然层级 | O(n²) 内存，951 算得动 | 已有 sklearn |

**Claude 倾向**: **B. MiniBatchKMeans**，性能可预测；如果 D-1 选自适应则用 C。

**你选**: ___

---

### D-3. Label & Summary 来源

每个 box 需要人类可读标签和摘要（否则就是一堆数字 box）。

| 选项 | 方式 | 成本 | 质量 |
|------|------|------|------|
| A. **纯规则** | 用 top rep_tags 拼成 label | 0 成本 | 机械，如 "windborne-os / OpenSpec" |
| B. **Gemma 生成** | 调 127.0.0.1:11435 | 单次 ~3s × 70 box = 3.5 min | 人类可读，如 "风隐OS 架构文档集" |
| C. **混合** | rep_tags 兜底，label 缺失时 Gemma 补 | 可并发，<2 min | 可靠 + 优雅 |
| D. **跳过** | 只存 rep_tags 列表 | 0 | 能导航但不友好 |

**Claude 倾向**: **B. Gemma 必须**，label + 30 字 summary 一次生成。Gemma 已经起了，边际成本低。

**你选**: ___

---

### D-4. 导航 API 集合

| 序号 | 操作 | 必要性 | 说明 |
|------|------|--------|------|
| 1 | `box_overview()` | **必** | 世界地图：列出所有 Region |
| 2 | `box_enter(box_id)` | **必** | 进入 box：列出子 box + 部分 docs |
| 3 | `box_focus(query)` | **必** | query 嵌入 → 最近 k 个 box |
| 4 | `box_around(box_id, k)` | **必** | centroid 邻居 |
| 5 | `box_contents(box_id)` | **必** | box 内所有 doc 列表 |
| 6 | `box_path(from_id, to_id)` | 可选 | 知识桥接路径 |
| 7 | `box_stats(box_id)` | 可选 | 质量指标 |
| 8 | `box_compare(a, b)` | 奢侈 | 两 box 主题差异 |
| 9 | `box_timeline(box_id)` | 奢侈 | box 内文档时间线 |

**Claude 倾向**: **前 7 个上线（含 path + stats），后 2 个先不做**。

**你选**: 保留 ___ / 去掉 ___

---

### D-5. 构建触发方式

| 选项 | 方式 | 适合 |
|------|------|------|
| A. **一次性脚本** | `python scripts/build_boxes.py` 手动跑 | MVP 够用 |
| B. **自动增量** | 每次 add_document 找最近 box 归入 | 好用但复杂 |
| C. **定时重建** | cron 每日凌晨重聚类 | 稳定但延迟 |
| D. **A + C 混合** | 初始 A，后续 C 重建 | 生产级 |

**Claude 倾向**: **先 A，记一张 TODO，生产级再做 D**。

**你选**: ___

---

### D-6. 质量指标阈值

构建完跑质量报告，不合格是告警还是阻断？

| 指标 | 阈值建议 | 不合格时 |
|------|----------|----------|
| 内聚度（组内平均距离） | < 0.35 | 告警 / 阻断 |
| 大小均衡（max/min） | < 15 | 告警 / 阻断 |
| tag 一致性（top tag 覆盖率） | > 0.40 | 告警 / 阻断 |
| 召回命中率（20 抽样） | > 0.80 | 告警 / 阻断 |

| 选项 | 行为 |
|------|------|
| A. **全告警** | 打印警告，box 照常用 |
| B. **全阻断** | 不合格不生成 box 表 |
| C. **混合** | 召回 < 0.5 阻断，其他告警 |

**Claude 倾向**: **A 告警**，不成熟就阻断会让 MVP 跑不起来，但必须打印报告供人判断。

**你选**: ___

---

### D-7. 持久化 & Schema

| 选项 | 存储 | 说明 |
|------|------|------|
| A. **新 LanceDB 表 `knowledge_boxes`** | 嵌入空间里直接存 centroid | 可以用 vector index 加速"找最近 box" |
| B. **存 collection 的 metadata_json** | 复用现有 collection 概念 | 不用新表但 query 不方便 |
| C. **JSON 文件** | `~/.xingtu-local/boxes.json` | 最简，但离开生态 |

**Claude 倾向**: **A. 新表**，LanceDB 原生向量检索，和现有架构对齐。

**你选**: ___

---

### D-8. MCP 工具命名前缀

| 选项 | 前缀 | 示例 |
|------|------|------|
| A. `xingtu_box_*` | 星图内置工具 | `xingtu_box_overview` |
| B. `knowledge_box_*` | 独立工具族 | `knowledge_box_overview` |
| C. `nav_*` | 强调"导航" | `nav_overview` |

**Claude 倾向**: **A. `xingtu_box_*`**，与现有 `xingtu_projection_l*` 对齐。

**你选**: ___

---

### D-9. Agent 使用提示

为了让 Claude 正确用 box 工具，是否注入 system prompt？

| 选项 | 方式 |
|------|------|
| A. **只暴露工具，不加提示** | 让 Claude 自己从 description 推断 |
| B. **MCP server instructions** | 在 MCP server 注册时带说明 |
| C. **CLAUDE.md 加指引** | 本地 CLAUDE.md 说"本地知识先用 box_* 导航" |

**Claude 倾向**: **B + C**，提升命中率。

**你选**: ___

---

### D-10. 交付方式

| 选项 | 方式 |
|------|------|
| A. **独立 PR** | 新分支 `feat/box-model` → review → merge | 
| B. **直接 commit 到 main** | 快但没 review | 
| C. **先本地验证再 PR** | 做完跑几天再开 PR |

**Claude 倾向**: **A. PR**，对齐之前 P0 流程，也便于回退。

**你选**: ___

---

## 决议汇总表 ✅ CONSENSUS

> **Matrix Discussion Room 决议** — 2026-04-21
> Topic ID: `topic-box-model-design-1776779377`
> Session ID: `inst-4451dc7348717172eb2fca54`
> Resolution ID: `res-4edf3ddf92bf18402666ecde`
> Resolution Type: **consensus** (5/5 agree)
> 参与者: lamport (chair) + knuth / torvalds / miyamoto (experts) + schneier (critic)

| 维度 | 决议 | 主张者 |
|------|------|--------|
| F-1 层级 | **3 层** (World → Region → Area → Docs) | 已定 |
| D-1 分支因子 | **B. 方正 1→10→60** (平均 16 doc/叶子 box) | knuth |
| D-2 聚类算法 | **B. MiniBatchKMeans** (可复现, 省内存, random_state=42 固定) | knuth |
| D-3 Label 来源 | **C. 混合** (rep_tags 兜底 + Gemma 补 label/summary, 失败保证 non-null) | miyamoto |
| D-4 API 集合 | **只上前 5 个**: overview / enter / focus / around / contents（path/stats/compare/timeline 不做） | torvalds |
| D-5 构建触发 | **A. 一次性脚本** (scripts/build_boxes.py, 增量 assign 延后, 重建脚本必须存在) | torvalds |
| D-6 质量阈值 | **双阈值**: cohesion<0.45 / 均衡<20 / 一致性>0.3 / 召回>0.7 告警；**召回<0.5 硬阻断**不生成 box 表 | knuth + schneier |
| D-7 持久化 | **A. 新 LanceDB 表 `knowledge_boxes`** (利用向量索引加速 box_focus) | knuth |
| D-8 命名前缀 | **A. `xingtu_box_*`** (对齐 projection_l0-l3) | torvalds |
| D-9 Agent 提示 | **B + C**: MCP instructions ("prefer box_focus over hybrid_search when tags unknown") + CLAUDE.md 加示例段 | miyamoto |
| D-10 交付方式 | **A. feat 分支 → PR → review → merge** (对齐 P0 流程) | torvalds |

### 🔒 schneier 4 条硬性约束（必须写进代码）

| # | 约束 | 落实点 |
|---|------|--------|
| 1 | `random_state=42` 固定，防 box 分配漂移 | `BoxBuilder.__init__` 默认 |
| 2 | 新文档超出 radius × 2 触发 `event_type=box_unassigned` | `BoxNavigator.assign()` |
| 3 | Gemma label 失败时 `rep_tags` 兜底必须 non-null | `BoxLabeler.generate()` try/except |
| 4 | 构建完输出质量报告 JSON，PR 描述引用数值否则 review 不过 | `scripts/build_boxes.py` + CI |

### 📊 重建触发（torvalds 补充）
- `unassigned 率 > 10%` 或 `累计 assign > 100` 触发重建建议
- 写入 `box.py:BoxNavigator.assign()` 的 side effect

---

---

## 实施清单（决议后启动）

- [ ] 1. `src/xingtu/models.py` + `KnowledgeBox` LanceModel (5 min)
- [ ] 2. `src/xingtu/box.py` BoxBuilder 聚类逻辑 (15 min)
- [ ] 3. `src/xingtu/box.py` BoxNavigator 操作 API (20 min)
- [ ] 4. Gemma label 生成器 (10 min)
- [ ] 5. `scripts/build_boxes.py` (5 min)
- [ ] 6. 全量构建 + 质量报告 (5 min)
- [ ] 7. `xingtu_box_*` MCP 工具 (10 min)
- [ ] 8. 端到端测试 + 示例 (10 min)
- [ ] 9. PR 提交 (5 min)

**总预估**: 85 min（含 Gemma 生成 label 等待）

---

## 快速决议模板

如果想快速全部采纳 Claude 倾向，可以回复：

> 全采纳默认，D-4 保留前 7 个，去掉 path/stats 之外的。

或按行逐个指定：

> D-1: B
> D-2: B
> D-3: C
> D-4: 全保留
> D-5: A
> D-6: A
> D-7: A
> D-8: A
> D-9: B+C
> D-10: A
