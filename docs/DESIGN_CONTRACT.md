# 星图 (XingTu) 设计契约

> **目的**: 确保 Pencil 设计与 SwiftUI 代码实现完全一致的中间约束文档  
> **版本**: 1.0.0  
> **最后更新**: 2026-01-29

---

## 一、设计系统规范

### 1.1 颜色系统

| Token | SwiftUI | Hex | 用途 |
|-------|---------|-----|------|
| `xingtuBackground` | `Color(red: 0.06, green: 0.06, blue: 0.10)` | `#0F0F1A` | 主背景 |
| `xingtuSecondaryBackground` | `Color.white.opacity(0.03)` | `#FFFFFF08` | 次级背景、卡片 |
| `xingtuAccent` | `Color(red: 0.4, green: 0.6, blue: 0.9)` | `#6699E6` | 主强调色 (风蓝) |
| `xingtuAccent.opacity(0.15)` | - | `#6699E626` | 轻强调背景 |
| `xingtuAccent.opacity(0.2)` | - | `#6699E633` | 标签背景 |
| `status.draft` | `.orange` | `#FF9500` | 草稿状态 |
| `status.confirmed` | `.blue` | `#007AFF` | 已确认状态 |
| `status.published` | `.green` | `#34C759` | 已发布状态 |
| `status.archived` | `.gray` | `#8E8E93` | 已归档状态 |
| `border.default` | `Color.white.opacity(0.1)` | `#FFFFFF1A` | 默认边框 |
| `border.active` | `Color(0.4, 0.6, 0.9).opacity(0.6)` | `#6699E699` | 激活边框 |

### 1.2 字体系统

| Token | SwiftUI | 大小 | 权重 | 用途 |
|-------|---------|------|------|------|
| `title.large` | `.largeTitle` | 34pt | `.bold` | 页面主标题 |
| `title.medium` | `.title2` | 22pt | `.bold` | 区块标题 |
| `headline` | `.headline` | 17pt | `.semibold` | 卡片标题、列表项 |
| `body` | `.body` | 17pt | `.regular` | 正文内容 |
| `subheadline` | `.subheadline` | 15pt | `.regular` | 辅助信息 |
| `caption` | `.caption` | 12pt | `.regular` | 小字说明 |
| `caption2` | `.caption2` | 11pt | `.medium` | 状态徽章 |
| `monospaced` | `.system(.body, design: .monospaced)` | 17pt | `.regular` | 代码/技术名称 |

### 1.3 间距系统

| Token | 值 | 用途 |
|-------|-----|------|
| `spacing.xs` | 4pt | 内部紧凑间距 |
| `spacing.sm` | 8pt | 元素内部间距 |
| `spacing.md` | 12pt | 组件间距 |
| `spacing.lg` | 16pt | 区块间距 |
| `spacing.xl` | 20pt | 大区块间距 |
| `spacing.xxl` | 24pt | 页面区块间距 |
| `padding.section` | 32pt | 章节内边距 |
| `padding.page` | 40pt | 页面内边距 |

### 1.4 圆角系统

| Token | 值 | 用途 |
|-------|-----|------|
| `radius.xs` | 4pt | 小标签、输入框 |
| `radius.sm` | 8pt | 按钮、输入框 |
| `radius.md` | 12pt | 卡片、模态框 |
| `radius.lg` | 16pt | 大卡片、拖放区域 |
| `radius.pill` | 999pt (Capsule) | 状态徽章、标签 |

---

## 二、组件规范

### 2.1 StatusBadge (状态徽章)

```
┌─────────────┐
│   草稿      │  ← font: caption2, fontWeight: medium
└─────────────┘
     ↑
  padding: 6px horizontal, 2px vertical
  background: status color (solid)
  foreground: white
  shape: Capsule (pill)
```

**Pencil 属性**:
```json
{
  "type": "frame",
  "layout": "horizontal",
  "padding": { "left": 6, "right": 6, "top": 2, "bottom": 2 },
  "fill": "#FF9500",
  "cornerRadius": 999,
  "children": [{
    "type": "text",
    "content": "草稿",
    "fontSize": 11,
    "fontWeight": 500,
    "fill": "#FFFFFF"
  }]
}
```

### 2.2 ObjectRowView (对象行)

```
┌──────────────────────────────────────────────────────────────────┐
│  [📊]  │  对象名称  ⌈草稿⌉                                        │
│  32px  │  ├ 150 行    2026-01-28 10:30                           │
└──────────────────────────────────────────────────────────────────┘
   ↑         ↑               ↑
 icon      headline       caption + secondary color
spacing: 12px between icon and content
padding: 4px vertical
```

**结构**:
- 外层 HStack, spacing: 12
- 图标: systemImage, font: title2, color: xingtuAccent, width: 32
- 内容 VStack, spacing: 4
  - 第一行 HStack: name (headline) + StatusBadge
  - 第二行 HStack, spacing: 8: 行数 Label + 时间 Text (caption, secondary)

### 2.3 ObjectHeader (对象头部)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [📊]   对象名称  ⌈草稿⌉              [AI 助手]  [确认]                  │
│  large   原始文件名                                                      │
│                                                                          │
│  📅 行数: 150     📆 创建时间: 2026-01-28     ✓ 确认时间: 2026-01-28    │
│                                                                          │
│  对象描述文本...                                                         │
│                                                                          │
│  ⌈标签1⌉  ⌈标签2⌉  ⌈标签3⌉                                              │
└──────────────────────────────────────────────────────────────────────────┘
```

**层级**:
- 外层 VStack, spacing: 16, padding: 16 (all)
- 第一区块 HStack, alignment: top
  - 左侧 HStack, spacing: 12: 图标 (largeTitle) + VStack (name + originalName)
  - Spacer
  - 右侧 HStack, spacing: 12: 操作按钮组
- 第二区块 HStack, spacing: 24: InfoItem 组
- 第三区块: 描述 Text (body, secondary)
- 第四区块 HStack: 标签组

### 2.4 InfoItem (信息项)

```
[📅]  创建时间:  2026-01-28 10:30
 ↑       ↑           ↑
icon   label      value
     secondary   primary
spacing: 4px
font: caption
```

### 2.5 EditablePropertyRow (可编辑属性行)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ [🔢] col_name  │  业务名称   │  INTEGER  │  ⌈主键⌉  │  0   │  150  │  1,2,3...  │  [✏️] │
│     140px      │    160px    │    80px   │  100px   │ 60px │  60px │   flex     │  50px │
└─────────────────────────────────────────────────────────────────────────────────────────┘
padding: 16px horizontal, 10px vertical
font: system size 13
background: selected ? xingtuAccent.opacity(0.1) : clear
```

**列规格**:
| 列名 | 宽度 | 对齐 | 内容 |
|------|------|------|------|
| 字段名 | 140px | leading | Icon + originalName |
| 业务名称 | 160px | leading | displayName (双击可编辑) |
| 数据类型 | 80px | leading | dataType.displayName (caption, secondary) |
| 语义类型 | 100px | leading | 标签或 "-" |
| 空值 | 60px | trailing | nullCount (orange if > 0) |
| 唯一值 | 60px | trailing | uniqueCount |
| 样本值 | flex | leading | sampleValues (caption, secondary) |
| 操作 | 50px | center | 编辑按钮 |

### 2.6 DropZoneView (拖放区域)

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                          [📄+]                                   │
│                     拖放 CSV 文件到此处                          │
│                     支持 CSV、TSV 格式                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**规格**:
- 最小高度: 200px
- 背景: `Color.white.opacity(0.03)` (normal) / `Color(0.4, 0.6, 0.9).opacity(0.15)` (dragging)
- 边框: 虚线 `strokeBorder(dash: [8, 4], lineWidth: 2)`
  - 颜色: `Color.white.opacity(0.1)` (normal) / `Color(0.4, 0.6, 0.9).opacity(0.6)` (dragging)
- 圆角: 16px
- 内边距: 32px
- 图标: font size 48, weight: light
- 标题: font size 16, weight: medium
- 副标题: font size 12, weight: light, opacity 0.5

### 2.7 AIAssistantView (AI 助手)

```
┌─────────────────────────────────────────┐
│  ✨  AI 元数据助手    ● 通义千问  ⚙️ 🗑️ │  ← header, height: 48
├─────────────────────────────────────────┤
│                                         │
│   ┌─────────────────────────────────┐   │
│   │ 欢迎消息卡片                    │   │  ← WelcomeMessage
│   │ ...                             │   │
│   └─────────────────────────────────┘   │
│                                         │
│                    ┌──────────────────┐ │
│                    │ 用户消息         │ │  ← 用户消息靠右
│                    └──────────────────┘ │
│   ┌──────────────────┐                  │
│   │ AI 回复          │                  │  ← AI消息靠左
│   │ ✓ 已执行 2 项修改│                  │
│   └──────────────────┘                  │
│                                         │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────┐  [⬆️]  │  ← input area
│  │ 描述修改...                  │       │
│  └─────────────────────────────┘        │
└─────────────────────────────────────────┘
     ↑
   width: 400px fixed
```

### 2.8 StatCard (统计卡片)

```
┌─────────────────────────────────────┐
│  [📊]   150                         │
│  40px   数据对象                    │
└─────────────────────────────────────┘
```

**规格**:
- 内边距: 16px (all)
- 最大宽度: fill
- 对齐: leading
- 背景: `color.opacity(0.1)`
- 圆角: 12px
- 图标: font title, color: theme color, width: 40
- 数值: font title2, fontWeight: bold
- 标题: font caption, color: secondary

---

## 三、布局规范

### 3.1 主布局结构

```
┌─────────────────────────────────────────────────────────────────────────┐
│ NavigationSplitView                                                      │
├────────────────────┬────────────────────────────────────────────────────┤
│                    │                                                    │
│   SidebarView      │              DetailView                            │
│                    │                                                    │
│   ┌──────────────┐ │   ┌────────────────────────────────────────────┐   │
│   │ 数据源       │ │   │                                            │   │
│   │  ├ 所有对象  │ │   │                                            │   │
│   │  ├ 草稿      │ │   │                                            │   │
│   │  ├ 已确认    │ │   │                                            │   │
│   │  └ 已发布    │ │   │                                            │   │
│   │              │ │   │                                            │   │
│   │ 视图        │ │   │                                            │   │
│   │  ├ 世界模型  │ │   │                                            │   │
│   │  └ 事件      │ │   │                                            │   │
│   └──────────────┘ │   └────────────────────────────────────────────┘   │
│                    │                                                    │
└────────────────────┴────────────────────────────────────────────────────┘
        ↑                                    ↑
  sidebar width              content area (flex)
   ~220px min
```

### 3.2 DataSourceListView 布局

```
┌─────────────────────────────────────────────────────────────────────────┐
│ NavigationSplitView                                                      │
├──────────────────────────────┬──────────────────────────────────────────┤
│                              │                                          │
│   List (inset style)         │       ObjectDetailView                   │
│                              │                                          │
│   ┌────────────────────────┐ │   ┌──────────────────────────────────┐   │
│   │ ObjectRowView          │ │   │ ObjectHeader                     │   │
│   │ ObjectRowView          │ │   ├──────────────────────────────────┤   │
│   │ ObjectRowView          │ │   │ Picker (segmented)               │   │
│   │ ...                    │ │   ├──────────────────────────────────┤   │
│   └────────────────────────┘ │   │ PropertiesListView / EventsView  │   │
│                              │   │                                  │   │
│   🔍 搜索数据源...           │   └──────────────────────────────────┘   │
│                              │                                          │
└──────────────────────────────┴──────────────────────────────────────────┘
```

### 3.3 ObjectDetailView 布局（带 AI 助手）

```
┌─────────────────────────────────────────────────────────────────────────┐
│ HStack                                                                   │
├───────────────────────────────────────────────────┬─────────────────────┤
│                                                   │                     │
│   VStack (主内容区)                               │   AIAssistantView   │
│                                                   │                     │
│   ┌─────────────────────────────────────────────┐ │   ┌───────────────┐ │
│   │ ObjectHeader                                │ │   │               │ │
│   ├─────────────────────────────────────────────┤ │   │               │ │
│   │ Picker (segmented)                          │ │   │               │ │
│   ├─────────────────────────────────────────────┤ │   │               │ │
│   │                                             │ │   │               │ │
│   │ EditablePropertiesListView                  │ │   │               │ │
│   │                                             │ │   │               │ │
│   └─────────────────────────────────────────────┘ │   └───────────────┘ │
│                                                   │        400px        │
│                  flex width                       │                     │
└───────────────────────────────────────────────────┴─────────────────────┘
```

---

## 四、动画与交互规范

### 4.1 动画系统

| Token | SwiftUI | 用途 |
|-------|---------|------|
| `xingtuSpring` | `.spring(response: 0.3, dampingFraction: 0.8)` | 标准弹性动画 |
| `easeInOut.fast` | `.easeInOut(duration: 0.2)` | 快速过渡 |
| `easeInOut.medium` | `.easeInOut(duration: 0.35)` | 中等过渡 |

### 4.2 拖放状态

| 状态 | 背景 | 边框 | 图标 |
|------|------|------|------|
| normal | `#FFFFFF08` | `#FFFFFF1A` dashed | `doc.badge.plus` |
| dragging | `#6699E626` | `#6699E699` dashed | `arrow.down.doc.fill` |
| processing | 不变 | 不变 | ProgressView |

### 4.3 选中状态

| 组件 | 正常背景 | 选中背景 |
|------|----------|----------|
| EditablePropertyRow | transparent | `xingtuAccent.opacity(0.1)` |
| List item | system default | system default |

---

## 五、图标映射

### 5.1 系统图标使用

| 场景 | SF Symbol | 备选 |
|------|-----------|------|
| 表/数据源 | `tablecells` | `cylinder` |
| CSV 文件 | `doc.text` | `doc` |
| 字段 | `field` | - |
| 添加 | `plus` | `plus.circle` |
| 刷新 | `arrow.clockwise` | - |
| AI/智能 | `sparkles` | `brain` |
| 设置 | `gearshape` | `gear` |
| 删除 | `trash` | - |
| 编辑 | `pencil` | `pencil.circle` |
| 确认 | `checkmark.circle` | `checkmark` |
| 发布 | `arrow.up.circle` | - |
| 草稿 | `doc.badge.clock` | - |
| 日期 | `calendar` | - |
| 链接/关系 | `link` | - |
| 图表 | `chart.bar` | - |
| 世界 | `globe` | - |
| 事件 | `clock.arrow.circlepath` | - |

### 5.2 数据类型图标

| 类型 | 图标 |
|------|------|
| string | `textformat` |
| integer | `number` |
| double | `number.circle` |
| boolean | `checkmark.square` |
| date | `calendar` |
| unknown | `questionmark.circle` |

### 5.3 对象类型图标

| 类型 | 图标 |
|------|------|
| table | `tablecells` |
| dimension | `cube` |
| fact | `chart.bar` |
| unknown | `questionmark.folder` |

---

## 六、Pencil MCP 使用指南

### 6.1 创建新设计文件

```bash
# 通过 MCP 工具
get_editor_state(include_schema: true)  # 获取 schema
open_document("new")                     # 创建新文件
```

### 6.2 设计工作流

1. **获取设计指南**:
   ```
   get_guidelines(topic: "design-system")
   ```

2. **创建画布结构**:
   ```javascript
   // batch_design operations
   mainScreen=I(document, {type: "frame", name: "星图主界面", width: 1440, height: 900, fill: "#0F0F1A"})
   sidebar=I(mainScreen, {type: "frame", name: "Sidebar", width: 240, height: "fill_container", fill: "#0F0F1A"})
   content=I(mainScreen, {type: "frame", name: "Content", layout: "vertical", width: "fill_container", height: "fill_container"})
   ```

3. **验证布局**:
   ```
   snapshot_layout()
   get_screenshot()
   ```

### 6.3 组件复用

从设计系统复制组件实例:
```javascript
statusBadge=C("StatusBadge", container, {descendants: {"label": {content: "草稿"}}})
```

---

## 七、契约验证检查清单

### 7.1 颜色检查
- [ ] 主背景使用 `#0F0F1A`
- [ ] 强调色使用 `#6699E6` (风蓝)
- [ ] 状态颜色符合规范 (草稿=橙, 确认=蓝, 发布=绿)

### 7.2 字体检查
- [ ] 标题使用 SF Pro Display
- [ ] 正文使用 SF Pro Text
- [ ] 等宽字体使用 SF Mono
- [ ] 字号符合规范

### 7.3 间距检查
- [ ] 组件间距使用 12/16/24px
- [ ] 内边距使用 8/12/16px
- [ ] 区块间距使用 20/24px

### 7.4 圆角检查
- [ ] 卡片圆角 12px
- [ ] 按钮圆角 8px
- [ ] 标签使用 Capsule

### 7.5 交互检查
- [ ] 拖放区域有 normal/dragging 两态
- [ ] 选中状态有背景高亮
- [ ] 动画使用弹性效果

---

## 八、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-01-29 | 初始版本，包含完整 UI 规范 |
