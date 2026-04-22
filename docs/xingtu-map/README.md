# 星图自述地图 (xingtu-map)

**定位**: Agent 加载这个地图，就知道星图 (Astrolabe) 自己能做什么、每个功能怎么调。

和 `docs/matrix-map/` 是**对称的**：那份讲 Matrix 怎么用，这份讲星图怎么用。

## 和 matrix-map 的区别

| | matrix-map | xingtu-map |
|---|------------|-----------|
| 对象 | Matrix 系统（外部） | 星图自己（本系统） |
| L2 节点 | **room** (多 agent 协作房间, 对应 Matrix room_key) | **organ** (功能模块, 对应星图五器官) |
| live 数据 | 从 `/api/admin/rooms` 同步 | 无 (组织模式是设计时定的) |
| parent_kind | area → room → operation | area → organ → operation |

## 五器官 (Areas → Organs)

```
area-xingtu-storage       (存储)      organ-collections / organ-documents
area-xingtu-retrieval     (检索)      organ-search / organ-projection
area-xingtu-trust-memory  (信任+记忆)  organ-trust / organ-memory
area-xingtu-matrix-bridge (Matrix 桥) organ-matrix-map
area-xingtu-admin         (治理)      organ-admin
```

## Agent 使用流程

```python
# 0. 初始化
from xingtu import XingTuService
svc = XingTuService(); svc.initialize()
mm = svc.matrix_map

# 1. 看星图能做什么
mm.overview()
# → {area_count, room_count, organ_count, operation_count, areas: [...]}

# 2. 进某个能力域
mm.enter_area("area-xingtu-retrieval")
# → {area, rooms, organs}   两个列表分开

# 3. 看某个 organ 详情 + 下辖 operation 列表
mm.get_organ("organ-xingtu-search")   # 等同 get_room，返回 kind=organ
# → {organ: {title, summary, module_path}, operations: [...]}

# 4. 看 operation 完整内容 (含 1-3 个 docs: curl / rule / diagram)
mm.get_operation("op-xingtu-hybrid-search")

# 5. 关键词搜
mm.find("trust")     # 三层搜索 + snake_case 拆词
```

## MCP 工具等价链路

在 Claude Code 或其他 MCP 客户端里：

```
xingtu_map_overview()
xingtu_map_enter_area(area_id)
xingtu_map_get_room(organ_id)      # 注: organ 走同一个 tool, 返回 kind=organ
xingtu_map_get_operation(op_id)
xingtu_map_find(query)
xingtu_map_graph(node_id)
```

## 导入

```bash
# 从 yaml 直连导入 (本进程)
python3 scripts/import_xingtu_map.py

# dry-run (不写数据)
python3 scripts/import_xingtu_map.py --dry-run
```

## 新增 organ / operation 的流程

1. **organ**: `organs/` 下新建 `<slug>.yaml`
   - 必填: `id / title / kind: organ / parent (= area id) / verified_at`
   - 建议: `module_path` 指向对应 Python 源文件
2. **operation**: 在 organ yaml 里追加到 `operations:`
   - 必填: `id / title / parent (= organ id) / verified_at / docs (1-3 条)`
3. `python3 scripts/import_xingtu_map.py` 导入
4. `mm.overview()` 验证

## 硬约束 (同 matrix-map)

1. operation 必须挂 **1-3 个 docs**
2. 每个节点必须有 `verified_at`
3. area 不能空（至少有 1 个 organ 或 room）
4. organ 不能空（至少有 1 个 operation）

## 和 Matrix 地图共享存储

两份地图共用 LanceDB 的 `collections / documents / relations` 表。
区分靠 `collection_type`：
- `map_area` 两边共用
- `map_room` Matrix 独有
- `map_organ` 星图独有

`mm.overview()` 同时返回两边的节点，从 id 前缀 `area-xingtu-*` vs `area-*` 区分。
