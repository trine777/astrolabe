# FYD MVP — 6 周路线图

> 起点: 2026-04-24 (本规范落地)
> 第一付费用户目标: 2026-06-05 (W6)
> 30 付费 PMF 目标: 2026-07-17 (W12)

## 总原则

1. **不写新基建** — 议会引擎 / 记忆 / Astrolabe 全用现有
2. **代码量上限 1500 行** — 主要是 Web 前端 + Stripe + 12 周调度
3. **Trine 自己 = 第一用户** — W1-W2 自己跑通完整流程, W3 写文章
4. **每周末 Friday gate** — 数据不达标当周即止, 不继续投入

---

## W0 (本周末, 2026-04-26 - 04-27)

**目标**: 议会能跑出可读的 FYD 风格报告 (产物验证, 不是工程验证)

| Task | Deliverable | 估时 |
|------|------------|------|
| FYD 议会 schema 落到 Astrolabe | 5 seats 注册 + persona 入库 | 2h |
| 跑一次自我议会 | Trine 用自己资源问卷过一次, 出报告 | 2h |
| 评估报告质量 | 5 维评分 (清晰/可执行/反对/具体/差异化) ≥ 4/5 | 1h |
| **Gate**: 报告质量 < 4/5 → 调 prompt 直到达标 | | |

**W0 不达标 → 整个 FYD 项目停**, 因为产品体验核心 = 议会输出质量.

---

## W1 (2026-04-28 - 05-04): 问卷 + 议会接入

| Task | Deliverable | 估时 |
|------|------------|------|
| 20 题资源问卷 schema | `QUESTIONNAIRE.yaml` 完整版 | 3h |
| 问卷填写 → 议会启动 API 链路 | `POST /fyd/start-discovery` 接通 | 4h |
| 议会跑完 → Astrolabe 存档 | 决议 + 报告 + 用户画像入库 | 3h |
| Trine 自跑一次完整链路 | 从问卷到报告 PDF 30 分钟出 | 2h |
| **Gate**: 端到端跑通且 Trine 满意报告 | | |

**Total**: 12h

---

## W2 (05-05 - 05-11): 报告生成 + Stripe

| Task | Deliverable | 估时 |
|------|------------|------|
| 议会报告 → PDF (复用 ppt_agent_room) | `POST /fyd/render-report` | 3h |
| Stripe 接入 (\$99 入会 + \$29/月) | Webhook 收款 + 用户开通 | 4h |
| 用户管理 (邮箱注册, magic link 登录) | 简单认证, 不用 OAuth | 3h |
| Free Trial 限制 (1 次议会) | 计数器 + 升级提示 | 2h |
| **Gate**: 完整闭环, Trine 朋友能注册付费拿到报告 | | |

**Total**: 12h

---

## W3 (05-12 - 05-18): 12 周陪跑机制

| Task | Deliverable | 估时 |
|------|------------|------|
| Weekly review schema | `weekly_review.yaml` 模板 | 2h |
| 定时调度 (cron / Matrix scheduler) | 每周一 09:00 触发用户 review | 4h |
| Review UI: 用户填进度 → 议会精简版跑 | 10 min 完成 | 5h |
| 用户档案页 ("我的创业史") | 时间线 + 历次决议 + 进度图 | 4h |
| **Gate**: Trine 自己已 W3 在用陪跑 | | |

**Total**: 15h

---

## W4 (05-19 - 05-25): Trine dogfooding + 文章

| Task | Deliverable | 估时 |
|------|------------|------|
| Trine 已用 FYD 4 周, 自己执行选定方向 | 真实用户案例 | (无新工时) |
| 写文章: 《我用我做的 AI 议会, 找到了 FYD》 | IndieHackers + HN draft | 6h |
| 录 30 秒产品 demo 视频 | TG/X 用 | 2h |
| Landing page (单页) | findyourdirection.dev (或类似) | 4h |
| 邀请 5 个独立开发者朋友试用 | 收 feedback, 不收钱 | 2h |
| **Gate**: 至少 1 个朋友说 "我会付费试" | | |

**Total**: 14h

---

## W5 (05-26 - 06-01): 公开发布

| Task | Deliverable | 估时 |
|------|------------|------|
| 发文章到 IndieHackers (周一) | 1 帖 | 1h |
| 发 Show HN (周三, 美国时间) | 1 帖 | 1h |
| Twitter thread (周二早) | 5-7 条 | 2h |
| Reddit r/indiehackers + r/Entrepreneur | 各 1 帖, 不广告口吻 | 1h |
| 24/7 监控 + 回评论 | 维持热度 3 天 | 8h |
| **Gate**: 5K+ 浏览, 50+ 试用, 5+ 付费 | | |

**Total**: 13h

---

## W6 (06-02 - 06-08): 迭代 + 第一个用户故事

| Task | Deliverable | 估时 |
|------|------------|------|
| 收集前 5 用户 feedback (面对面 30 min/人) | feedback 汇总 | 5h |
| 修最痛 3 个 bug / 体验问题 | 直接 commit | 6h |
| 公开第一个用户故事 (匿名/实名) | "User #1: how X used FYD to ship" | 3h |
| 问卷 v2 (基于 feedback 微调) | 题目调整 | 2h |
| **Gate**: 30 付费 (✓ PMF) 或 < 5 付费 (Kill 信号) | | |

**Total**: 16h

---

## 总工时

| 周 | 工时 |
|----|------|
| W0 | 5h |
| W1 | 12h |
| W2 | 12h |
| W3 | 15h |
| W4 | 14h |
| W5 | 13h |
| W6 | 16h |
| **Total** | **87h** (≈ 14h/周, 6 周) |

按每周 14h (周末 + 工作日晚饭后), 是独立开发者副业级强度. 不挤占 Astrolabe 维护.

---

## 关键 Friday Gate (每周末 30 min review)

每周五晚 9 点, 自评 3 个数字:

| 周 | 必须达成 |
|----|---------|
| W0 | 议会报告自评 ≥ 4/5 |
| W1 | 端到端 30 min 跑通 |
| W2 | 至少 1 个真朋友付费 \$99 |
| W3 | 自己已陪跑 3 周 |
| W4 | 至少 1 个朋友说"愿付费" |
| W5 | 5K 曝光 + 5 付费 |
| W6 | 30 付费 OR 真 Kill |

不达 → 当周末判定停 / 调整, 不允许"再多做一周看看".

---

## 不在本路线图里的 (W7+)

- Public Council (旁观他人议会)
- 议会个性化命名/微调
- 多议会主题 (用户开多个并行)
- 数据导入 (绑业务数据触发周回顾)
- Annual Plan
- B2B / 团队议会

这些都看 W6 数据决定. **PMF 信号不明前不做.**

---

## 第一个里程碑庆祝点

W2 末: 第一个朋友付 \$99 → Trine 拿到第一笔 FYD 收入 (产品的, 不是顾问/外包).
这一刻是 8 个月以来第一次"产品收入", 是真信号.
