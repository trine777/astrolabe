# FYD — FindYourDirection

**给独立开发者的 12 周 AI 议会陪跑.**

---

## 这是什么

不是工具, 不是 SaaS dashboard. 是一个 **12 周陪跑产品**:

1. 你填一份 20 题资源问卷 (10-15 分钟)
2. AI 5 人议会跑 30 分钟, 给你 3-5 个候选业务方向 + 验证步骤 + 反对意见
3. 你选 1 个方向
4. 接下来 12 周, 议会每周 review 你的进度, 给路径调整
5. 12 周末出"你的创业史"档案

Trine (我自己) 是第 1 个用户. 本会话就是这个产品的真实 demo.

---

## 文档导航

| 文件 | 作用 |
|------|------|
| `PRODUCT_SPEC.md` | 产品规范 (定位/用户/旅程/4 条硬约束/商业模型) |
| `COUNCIL_SCHEMA.yaml` | 议会 5 seats 人格定义 + 议会输出格式 |
| `QUESTIONNAIRE.yaml` | 20 题用户问卷 v0.1 |
| `ROADMAP.md` | 6 周 MVP 路线图 + Friday Gate |
| `README.md` | 本文件 |

---

## 关键决议来源

Matrix Discussion `inst-57e5716b1f5585a8f48ba3e2`
Resolution `res-37413e98ee81e89201b58aab` (5/5 consensus)
2026-04-24

参与者: lamport (chair) + drucker / graham / bezos (experts) + thiel (critic)

---

## 4 条硬约束 (产品级红线)

1. **垂直锁死 12 个月** — 只做"独立开发者找业务方向", 不做通用决策
2. **议会不给"你应该做 X"** — 永远是候选 + 利弊 + 验证 + 决策权用户
3. **必须有真反对派 critic** — 5 seats 里 critic 必须真反对至少 1 个候选
4. **12 周末必填 final review** — 数据回流是真护城河

---

## 4-6 周 MVP 起点

- W0 (本周末): 议会能跑出 ≥ 4/5 质量报告
- W1: 问卷 + 议会接入端到端 30 min 跑通
- W2: Stripe + 第 1 个朋友付费
- W3: 12 周陪跑机制
- W4: Trine 写文章 + landing page
- W5: HN/IndieHackers 公开发布
- W6: 30 付费 (PMF) 或 Kill

详见 `ROADMAP.md`.

---

## 价格 (v0)

| SKU | 价格 |
|-----|------|
| Free Trial | \$0 (1 次议会) |
| Onboarding | \$99 一次性 (含 1 月陪跑) |
| Continuing | \$29/月 |
| Annual | \$299/年 (省 \$108) |

---

## 与 Astrolabe 的关系

FYD 是 Astrolabe + Matrix 矩阵的**第一个面向终端用户的核心产品**.

不是新代码项目, 是**把现有基建对着用户视角输出**:

- 议会引擎 = `discussion-room-wide-v1` (Matrix 现成)
- 用户画像 + 决议档案 = `Astrolabe` (现成)
- LLM = `Gemma 4-31B 本地` (现成)
- 报告生成 = `ppt_agent_room` (现成)

新增代码上限 1500 行 (主要是 Web 前端 + Stripe + 12 周调度).

---

## 不在 v0 范围

- Public Council (旁观他人议会)
- 议会个性化命名/微调
- 多议会主题
- 数据导入触发周回顾
- B2B / 团队议会
- 通用决策 (感情/职业/团队)

W6 数据决定是否扩展.
