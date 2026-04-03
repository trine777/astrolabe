"""
星图 XingTu - MCP Server

为 AI Agent 提供多模态数据库能力的 MCP 协议服务器。
使用 FastMCP 框架实现。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from xingtu import XingTuService
from xingtu.config import XingTuConfig

logger = logging.getLogger(__name__)

# 创建 MCP 服务器实例
mcp = FastMCP("xingtu")

# 全局服务实例（延迟初始化）
_service: Optional[XingTuService] = None


def get_service() -> XingTuService:
    """获取或创建 XingTuService 实例"""
    global _service
    if _service is None:
        config = XingTuConfig.from_env()
        _service = XingTuService(config)
        _service.initialize()
    return _service


def _json(obj: Any) -> str:
    """统一 JSON 序列化"""
    return json.dumps(obj, ensure_ascii=False, default=str)


def _clean(d: dict) -> dict:
    """清理 LanceDB 内部字段"""
    return {k: v for k, v in d.items() if not k.startswith("_")}


# ===== 集合管理工具 =====


@mcp.tool()
def xingtu_create_collection(
    name: str,
    description: str = "",
    collection_type: str = "documents",
    tags: Optional[list[str]] = None,
) -> str:
    """创建数据集合（同名幂等，返回已有集合）。

    Args:
        name: 集合名称
        description: 集合描述
        collection_type: 集合类型 (documents, images, audio, multimodal, structured, knowledge)
        tags: 标签列表
    """
    service = get_service()
    result = service.create_collection(
        name=name,
        description=description or None,
        collection_type=collection_type,
        tags=tags,
        created_by="ai",
    )
    return _json(result)


@mcp.tool()
def xingtu_list_collections(
    status: Optional[str] = None,
    collection_type: Optional[str] = None,
) -> str:
    """列出所有数据集合。

    Args:
        status: 按状态过滤 (draft, confirmed, published, archived)
        collection_type: 按类型过滤
    """
    service = get_service()
    results = service.list_collections(status=status, collection_type=collection_type)
    return _json([_clean(r) for r in results])


@mcp.tool()
def xingtu_get_collection(collection_id: str) -> str:
    """获取集合详情。

    Args:
        collection_id: 集合 ID
    """
    service = get_service()
    result = service.get_collection(collection_id)
    if result is None:
        return _json({"error": f"Collection {collection_id} not found"})
    return _json(_clean(result))


@mcp.tool()
def xingtu_update_collection(
    collection_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """更新集合信息。

    Args:
        collection_id: 集合 ID
        name: 新名称
        description: 新描述
        status: 新状态 (draft, confirmed, published, archived)
        tags: 新标签列表
    """
    service = get_service()
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if status is not None:
        kwargs["status"] = status
    if tags is not None:
        kwargs["tags"] = tags
    result = service.update_collection(collection_id, **kwargs)
    if result is None:
        return _json({"error": f"Collection {collection_id} not found"})
    return _json(_clean(result))


@mcp.tool()
def xingtu_delete_collection(collection_id: str) -> str:
    """删除集合及其所有文档。

    Args:
        collection_id: 集合 ID
    """
    service = get_service()
    service.delete_collection(collection_id)
    return _json({"status": "deleted", "collection_id": collection_id})


# ===== 文档操作工具 =====


@mcp.tool()
def xingtu_add_documents(
    collection_id: str,
    texts: list[str],
) -> str:
    """向集合添加文档（自动生成嵌入向量）。

    Args:
        collection_id: 目标集合 ID
        texts: 文本内容列表
    """
    service = get_service()
    result = service.add_documents(collection_id, texts, created_by="ai")
    return _json(result.model_dump())


@mcp.tool()
def xingtu_get_document(document_id: str) -> str:
    """获取文档详情。

    Args:
        document_id: 文档 ID
    """
    service = get_service()
    result = service.get_document(document_id)
    if result is None:
        return _json({"error": f"Document {document_id} not found"})
    cleaned = {k: v for k, v in result.items() if not k.startswith("_") and k != "vector"}
    return _json(cleaned)


@mcp.tool()
def xingtu_update_document(
    document_id: str,
    content: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata_json: Optional[str] = None,
) -> str:
    """更新文档信息。

    Args:
        document_id: 文档 ID
        content: 新内容
        tags: 新标签
        metadata_json: 新元数据 JSON
    """
    service = get_service()
    kwargs = {}
    if content is not None:
        kwargs["content"] = content
    if tags is not None:
        kwargs["tags"] = tags
    if metadata_json is not None:
        kwargs["metadata_json"] = metadata_json
    result = service.update_document(document_id, **kwargs)
    if result is None:
        return _json({"error": f"Document {document_id} not found"})
    cleaned = {k: v for k, v in result.items() if not k.startswith("_") and k != "vector"}
    return _json(cleaned)


@mcp.tool()
def xingtu_delete_documents(
    collection_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> str:
    """删除文档。

    Args:
        collection_id: 按集合 ID 删除所有文档
        document_id: 按文档 ID 删除单个文档
    """
    service = get_service()
    if document_id:
        service.delete_documents(f"id = '{document_id}'")
        return _json({"status": "deleted", "document_id": document_id})
    elif collection_id:
        service.delete_documents(f"collection_id = '{collection_id}'")
        return _json({"status": "deleted", "collection_id": collection_id})
    else:
        return _json({"error": "Must specify collection_id or document_id"})


@mcp.tool()
def xingtu_ingest_file(
    file_path: str,
    collection_id: Optional[str] = None,
) -> str:
    """导入文件到星图（支持 CSV、JSON、PDF、TXT、图片）。

    Args:
        file_path: 文件路径
        collection_id: 目标集合 ID（不指定则自动创建）
    """
    service = get_service()
    result = service.ingest_file(file_path, collection_id, created_by="ai")
    return _json(result.model_dump())


# ===== 搜索工具 =====


@mcp.tool()
def xingtu_vector_search(
    query: str,
    collection_id: Optional[str] = None,
    limit: int = 10,
) -> str:
    """向量语义搜索 - 基于语义相似度检索文档。

    Args:
        query: 搜索查询文本
        collection_id: 限定搜索的集合 ID
        limit: 返回结果数量
    """
    service = get_service()
    results = service.search(query, search_type="vector", collection_id=collection_id, limit=limit)
    return _json(results)


@mcp.tool()
def xingtu_text_search(
    query: str,
    collection_id: Optional[str] = None,
    limit: int = 10,
) -> str:
    """全文关键词搜索 - 基于关键词匹配检索文档。

    Args:
        query: 搜索关键词
        collection_id: 限定搜索的集合 ID
        limit: 返回结果数量
    """
    service = get_service()
    results = service.search(query, search_type="text", collection_id=collection_id, limit=limit)
    return _json(results)


@mcp.tool()
def xingtu_hybrid_search(
    query: str,
    collection_id: Optional[str] = None,
    limit: int = 10,
    reranker: str = "rrf",
) -> str:
    """混合搜索 - 结合向量语义和全文关键词的搜索。

    Args:
        query: 搜索查询
        collection_id: 限定搜索的集合 ID
        limit: 返回结果数量
        reranker: 重排序策略 (rrf 或 linear)
    """
    service = get_service()
    results = service.search(
        query, search_type="hybrid", collection_id=collection_id,
        limit=limit, reranker=reranker,
    )
    return _json(results)


@mcp.tool()
def xingtu_find_similar(
    document_id: str,
    limit: int = 10,
    collection_id: Optional[str] = None,
) -> str:
    """查找与指定文档相似的文档。

    Args:
        document_id: 源文档 ID
        limit: 返回结果数量
        collection_id: 限定搜索的集合 ID
    """
    service = get_service()
    results = service.find_similar(document_id, limit=limit, collection_id=collection_id)
    return _json(results)


# ===== 关系工具 =====


@mcp.tool()
def xingtu_create_relation(
    source_id: str,
    target_id: str,
    relation_type: str = "related_to",
    description: Optional[str] = None,
    confidence: float = 1.0,
) -> str:
    """创建数据关系。

    Args:
        source_id: 源文档/集合 ID
        target_id: 目标文档/集合 ID
        relation_type: 关系类型 (references, derived_from, similar_to, part_of, contains, related_to)
        description: 关系描述
        confidence: 置信度 0-1
    """
    service = get_service()
    result = service.create_relation(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        description=description,
        confidence=confidence,
        is_ai_inferred=True,
    )
    return _json(_clean(result))


@mcp.tool()
def xingtu_get_relations(
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
    relation_type: Optional[str] = None,
) -> str:
    """查询数据关系。

    Args:
        source_id: 按源 ID 过滤
        target_id: 按目标 ID 过滤
        relation_type: 按关系类型过滤
    """
    service = get_service()
    results = service.get_relations(
        source_id=source_id, target_id=target_id, relation_type=relation_type,
    )
    return _json([_clean(r) for r in results])


@mcp.tool()
def xingtu_delete_relation(relation_id: str) -> str:
    """删除关系。

    Args:
        relation_id: 关系 ID
    """
    service = get_service()
    service.delete_relation(relation_id)
    return _json({"status": "deleted", "relation_id": relation_id})


# ===== Agent 记忆工具 =====


@mcp.tool()
def xingtu_store_memory(
    agent_id: str,
    content: str,
    memory_type: str = "semantic",
    importance: float = 0.5,
    tags: Optional[list[str]] = None,
) -> str:
    """存储 Agent 记忆。

    Args:
        agent_id: Agent 标识
        content: 记忆内容
        memory_type: 记忆类型 (working, episodic, semantic, procedural)
        importance: 重要性评分 0-1
        tags: 标签列表
    """
    service = get_service()
    result = service.store_memory(
        agent_id=agent_id,
        content=content,
        memory_type=memory_type,
        importance=importance,
        tags=tags,
    )
    cleaned = {k: v for k, v in result.items() if not k.startswith("_") and k != "vector"}
    return _json(cleaned)


@mcp.tool()
def xingtu_recall_memories(
    agent_id: str,
    query: str,
    memory_type: Optional[str] = None,
    limit: int = 10,
) -> str:
    """检索 Agent 记忆 - 基于语义相似度召回相关记忆。

    Args:
        agent_id: Agent 标识
        query: 检索查询
        memory_type: 按记忆类型过滤
        limit: 返回数量
    """
    service = get_service()
    results = service.recall_memories(
        agent_id=agent_id, query=query, memory_type=memory_type, limit=limit,
    )
    return _json(results)


@mcp.tool()
def xingtu_forget_memories(
    agent_id: str,
    memory_type: Optional[str] = None,
) -> str:
    """遗忘 Agent 记忆。

    Args:
        agent_id: Agent 标识
        memory_type: 按类型遗忘（不指定则遗忘全部）
    """
    service = get_service()
    service.forget_memories(agent_id=agent_id, memory_type=memory_type)
    return _json({
        "status": "forgotten",
        "agent_id": agent_id,
        "memory_type": memory_type or "all",
    })


@mcp.tool()
def xingtu_get_memory_stats(agent_id: str) -> str:
    """获取 Agent 记忆统计。

    Args:
        agent_id: Agent 标识
    """
    service = get_service()
    result = service.get_memory_stats(agent_id)
    return _json(result)


# ===== 分层投影工具 =====


@mcp.tool()
def xingtu_projection_l0(limit: int = 20, offset: int = 0) -> str:
    """L0 位面索引 — 系统全局概览。

    返回所有集合（位面）的索引，适合冷启动了解系统全貌。
    Token 开销约 ~400。

    Args:
        limit: 最多返回多少位面（默认 20）
        offset: 跳过前 N 个
    """
    service = get_service()
    return _json(service.projection_l0(limit=limit, offset=offset))


@mcp.tool()
def xingtu_projection_l1(
    collection_id: str,
    limit: int = 30,
    offset: int = 0,
) -> str:
    """L1 位面概览 — 单个位面的元信息 + 实体列表。

    Token 开销约 ~500。

    Args:
        collection_id: 集合 ID
        limit: 最多返回多少实体（默认 30）
        offset: 跳过前 N 个
    """
    service = get_service()
    return _json(service.projection_l1(collection_id, limit=limit, offset=offset))


@mcp.tool()
def xingtu_projection_l2(document_id: str) -> str:
    """L2 实体详情 — 单个实体的完整信息和元数据。

    Token 开销约 ~200。

    Args:
        document_id: 文档 ID
    """
    service = get_service()
    return _json(service.projection_l2(document_id))


@mcp.tool()
def xingtu_projection_l3(
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
    relation_type: Optional[str] = None,
    limit: int = 50,
) -> str:
    """L3 关系图 — 实体/位面间的关系网络。

    支持悬空关系检测。Token 开销约 ~300。

    Args:
        source_id: 按源过滤
        target_id: 按目标过滤
        relation_type: 按关系类型过滤
        limit: 最多返回多少条
    """
    service = get_service()
    return _json(service.projection_l3(
        source_id=source_id, target_id=target_id,
        relation_type=relation_type, limit=limit,
    ))


# ===== 信任评估工具 =====


@mcp.tool()
def xingtu_evaluate_trust(item_id: str) -> str:
    """评估单个实体的信任度。

    五维加权评分：来源权威性(25%)、时效性(20%)、交叉引用密度(20%)、确认状态(20%)、审计覆盖(15%)。
    缺少证据的维度使用中立值 0.5，不惩罚新数据。

    Args:
        item_id: 文档或集合 ID
    """
    service = get_service()
    return _json(service.evaluate_trust(item_id))


@mcp.tool()
def xingtu_batch_evaluate_trust(item_ids: list[str]) -> str:
    """批量信任评估。

    逐条评估，单条失败不影响其他条目。

    Args:
        item_ids: 文档/集合 ID 列表
    """
    service = get_service()
    return _json(service.batch_evaluate_trust(item_ids))


@mcp.tool()
def xingtu_detect_cross_references(
    item_id: str,
    threshold: float = 0.85,
    max_edges: int = 10,
) -> str:
    """检测并创建交叉引用关系。

    用语义相似度发现近邻文档，自动创建 similar_to 关系。
    内置去重、方向归一化、边数上限防护。

    Args:
        item_id: 文档 ID
        threshold: 相似度阈值 0-1（默认 0.85）
        max_edges: 每 item 最多创建的边数（默认 10）
    """
    service = get_service()
    return _json(service.detect_cross_references(
        item_id, threshold=threshold, max_edges=max_edges,
    ))


# ===== 系统工具 =====


@mcp.tool()
def xingtu_get_world_model() -> str:
    """获取星图世界模型 — 包含所有集合、文档统计、关系和最近事件的完整视图。
    注意：大规模数据下请用 projection_l0-l3 逐层钻入。"""
    service = get_service()
    return _json(service.get_world_model())


@mcp.tool()
def xingtu_get_events(
    target_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
) -> str:
    """查询事件历史（审计轨迹）。

    Args:
        target_id: 按目标 ID 过滤
        event_type: 按事件类型过滤 (created, updated, deleted, searched, inferred, confirmed)
        limit: 返回数量
    """
    service = get_service()
    results = service.get_events(target_id=target_id, event_type=event_type, limit=limit)
    return _json(results)


@mcp.tool()
def xingtu_get_stats() -> str:
    """获取星图系统统计 — 各表行数。"""
    service = get_service()
    return _json(service.get_stats())


@mcp.tool()
def xingtu_optimize() -> str:
    """优化星图数据库 — 压缩文件、清理旧版本。"""
    service = get_service()
    return _json(service.optimize())


# ===== 小世界模型 - 意图驱动工具 =====


@mcp.tool()
def xingtu_intent(
    intent_text: str,
    user_id: str = "ai",
    auto_execute: bool = True,
) -> str:
    """处理人类意图 — 小世界模型核心入口。

    流程: 自然语言 → 结构化目标 → 差分计算 → 自动执行。

    Args:
        intent_text: 用户的自然语言意图
        user_id: 用户标识
        auto_execute: 是否自动执行（默认 True）
    """
    service = get_service()
    result = service.universe.process_intent(
        intent_text=intent_text,
        user_id=user_id,
        auto_execute=auto_execute,
    )
    return _json(result)


@mcp.tool()
def xingtu_get_goal_status(goal_id: str) -> str:
    """获取目标执行状态。

    Args:
        goal_id: 目标 ID
    """
    service = get_service()
    return _json(service.universe.get_goal_status(goal_id))


@mcp.tool()
def xingtu_execute_delta(delta_id: str) -> str:
    """手动执行单个差分。

    Args:
        delta_id: 差分 ID
    """
    service = get_service()
    return _json(service.universe.execute_delta(delta_id))


@mcp.tool()
def xingtu_list_pending_goals() -> str:
    """列出所有待处理的目标。"""
    service = get_service()
    return _json(service.universe.list_pending_goals())


@mcp.tool()
def xingtu_list_pending_deltas() -> str:
    """列出所有待执行的差分。"""
    service = get_service()
    return _json(service.universe.list_pending_deltas())


# ===== MCP 资源 =====


@mcp.resource("xingtu://world-model")
def resource_world_model() -> str:
    """星图世界模型 - 完整数据视图"""
    service = get_service()
    return _json(service.get_world_model())


@mcp.resource("xingtu://collections")
def resource_collections() -> str:
    """星图集合列表"""
    service = get_service()
    results = service.list_collections()
    return _json([_clean(r) for r in results])


@mcp.resource("xingtu://stats")
def resource_stats() -> str:
    """星图系统统计"""
    service = get_service()
    return _json(service.get_stats())


# ===== 入口点 =====


def main():
    """MCP Server 入口"""
    logging.basicConfig(level=logging.INFO)
    logger.info("星图 XingTu MCP Server 启动中...")
    mcp.run()


if __name__ == "__main__":
    main()
