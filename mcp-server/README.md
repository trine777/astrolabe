# 星图 MCP Server

> 让 AI 也能使用星图数据系统

## 定位

星图 MCP Server 是 XingTu 的 AI 接口层，让 Claude 等 AI 可以：

- 查看和管理数据源对象
- 读写元数据属性
- 提议和确认数据关系
- 记录洞察到影澜轩
- 查询世界模型

## 安装

```bash
cd /Users/trine/风隐元枢/aeolian_station/xingtu/mcp-server
pip install -e .
```

## 配置 Cursor

在 Cursor 设置中添加 MCP Server：

```json
{
  "mcpServers": {
    "xingtu": {
      "command": "python",
      "args": ["-m", "xingtu_mcp.server"],
      "cwd": "/Users/trine/风隐元枢/aeolian_station/xingtu/mcp-server"
    }
  }
}
```

或者使用安装后的命令：

```json
{
  "mcpServers": {
    "xingtu": {
      "command": "xingtu-mcp"
    }
  }
}
```

## 可用工具

### 对象管理

| 工具 | 说明 |
|------|------|
| `xingtu_list_objects` | 列出所有数据源 |
| `xingtu_get_object` | 获取对象详情（含属性、关系） |
| `xingtu_create_object` | 创建新对象 |
| `xingtu_update_object` | 更新对象信息 |
| `xingtu_confirm_object` | 确认对象元数据 |
| `xingtu_publish_object` | 发布对象 |

### 属性管理

| 工具 | 说明 |
|------|------|
| `xingtu_get_properties` | 获取对象的所有属性 |
| `xingtu_create_property` | 创建新属性 |
| `xingtu_update_property` | 更新属性（语义类型、描述等） |

### 关系管理

| 工具 | 说明 |
|------|------|
| `xingtu_get_relations` | 获取对象的关系 |
| `xingtu_create_relation` | 创建关系（AI 提议） |
| `xingtu_confirm_relation` | 确认关系 |

### 事件与世界模型

| 工具 | 说明 |
|------|------|
| `xingtu_get_events` | 获取事件历史 |
| `xingtu_emit_event` | AI 发送事件 |
| `xingtu_get_world_model` | 获取完整世界模型 |

## 可用资源

| URI | 说明 |
|-----|------|
| `xingtu://world-model` | 世界模型（已发布的对象、属性、关系） |
| `xingtu://objects` | 数据源列表 |

## 数据库

MCP Server 与 XingTuApp (Swift) 共享同一个 SQLite 数据库：

```
~/Library/Application Support/XingTu/xingtu.db
```

## 人机协作流程

```
1. 人类在 XingTuApp 拖入 CSV
   ↓
2. AI 通过 MCP 调用 xingtu_list_objects 发现新数据
   ↓
3. AI 调用 xingtu_update_property 推断语义类型
   ↓
4. 人类在 GUI 审核 AI 的推断
   ↓
5. 人类/AI 调用 xingtu_confirm_object
   ↓
6. 人类调用 xingtu_publish_object
   ↓
7. AI 可以查询 xingtu_get_world_model 使用数据
```

## 作者

- Owner: Claude (AI)
- 验收: Trine (Human)

---

*版本: 0.1.0*
*创建时间: 2026-01-30*
