"""
星图 XingTu v2 - 多模态 Agent 数据库

为 AI Agent 设计的数据基础设施，支持多模态数据的存储、检索、关联。

核心组件（五器官架构）：
- 星空座 (XingkongzuoStore): 存储核心 - LanceDB 存储层
- 语界枢 (YujieshuIngest): 输入通道 - 多模态数据摄入
- 炽心核 (ChixinheSearch): 执行核心 - 搜索与决策引擎
- 影澜轩 (YinglanxuanEvents): 感知核心 - 事件流与审计
- 序律腺 (XuluxianScheduler): 调度核心 - 任务调度

使用方式：
    from xingtu import XingTuService

    service = XingTuService()
    service.initialize()

    # 创建集合
    col = service.create_collection("my-data", "我的数据集")

    # 导入数据
    result = service.ingest_file("data.csv", col["id"])

    # 搜索
    results = service.search("查询内容")
"""

from __future__ import annotations

__version__ = "2.0.0"

import logging
import uuid
from typing import List, Optional

from .config import XingTuConfig
from .embeddings import EmbeddingManager
from .events import YinglanxuanEvents
from .models import (
    AgentMemory,
    Collection,
    CollectionStatus,
    CollectionType,
    ContentType,
    Document,
    Event,
    IngestResult,
    MemoryStats,
    Relation,
    SearchResult,
    WorldModel,
    now_iso,
)
from .scheduler import XuluxianScheduler
from .store import XingkongzuoStore
from .universe import UniverseModel

logger = logging.getLogger(__name__)


class XingTuService:
    """
    星图服务 - 统一入口

    协调五器官，提供完整的多模态 Agent 数据库能力。

    v2.0 新增：小世界模型 - 意图驱动的主权智能体
    """

    def __init__(self, config: Optional[XingTuConfig] = None):
        self.config = config or XingTuConfig.default()

        # 初始化五器官
        self.store = XingkongzuoStore(self.config.store.db_path)
        self.embedding_manager = EmbeddingManager(self.config.embedding)
        self.events: Optional[YinglanxuanEvents] = None
        self.scheduler = XuluxianScheduler()

        # 延迟初始化的组件
        self._search = None
        self._ingest = None
        self._initialized = False

        # 小世界模型（意图驱动）
        self.universe: Optional[UniverseModel] = None

    def initialize(self) -> None:
        """初始化所有组件"""
        if self._initialized:
            return

        logger.info("星图 XingTu v2 初始化中...")

        # 初始化存储
        self.store.initialize()

        # 初始化嵌入管理器
        self.embedding_manager.initialize()

        # 初始化事件流
        self.events = YinglanxuanEvents(self.store)

        # 延迟导入避免循环依赖
        from .ingest import YujieshuIngest
        from .search import ChixinheSearch

        self._search = ChixinheSearch(self.store, self.embedding_manager)
        self._ingest = YujieshuIngest(self.store, self.embedding_manager)

        # 初始化小世界模型
        from .intent import IntentTranslator
        from .delta import DeltaGenerator

        intent_translator = IntentTranslator(
            embedding_manager=self.embedding_manager
        )
        delta_generator = DeltaGenerator()

        self.universe = UniverseModel(
            store=self.store,
            intent_translator=intent_translator,
            delta_generator=delta_generator,
        )

        self._initialized = True
        logger.info("星图 XingTu v2 初始化完成（含小世界模型）")

        # 记录初始化事件
        self.events.emit(
            event_type="created",
            target_type="system",
            description="星图 XingTu v2 已初始化",
        )

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            self.initialize()

    # ===== 集合管理 =====

    def create_collection(
        self,
        name: str,
        description: Optional[str] = None,
        collection_type: str = "documents",
        tags: Optional[List[str]] = None,
        created_by: str = "system",
        metadata_json: Optional[str] = None,
    ) -> dict:
        """创建数据集合"""
        self._ensure_initialized()
        collection_id = str(uuid.uuid4())
        result = self.store.create_collection(
            id=collection_id,
            name=name,
            description=description,
            collection_type=collection_type,
            tags=tags,
            created_by=created_by,
            metadata_json=metadata_json,
        )
        self.events.emit(
            event_type="created",
            target_type="collection",
            target_id=collection_id,
            actor_type=created_by,
            description=f"创建集合: {name}",
        )
        return result

    def get_collection(self, collection_id: str) -> Optional[dict]:
        """获取集合详情"""
        self._ensure_initialized()
        return self.store.get_collection(collection_id)

    def list_collections(
        self,
        status: Optional[str] = None,
        collection_type: Optional[str] = None,
    ) -> List[dict]:
        """列出集合"""
        self._ensure_initialized()
        return self.store.list_collections(status=status, collection_type=collection_type)

    def update_collection(self, collection_id: str, **kwargs) -> Optional[dict]:
        """更新集合"""
        self._ensure_initialized()
        result = self.store.update_collection(collection_id, **kwargs)
        if result:
            self.events.emit(
                event_type="updated",
                target_type="collection",
                target_id=collection_id,
                description=f"更新集合字段: {list(kwargs.keys())}",
            )
        return result

    def delete_collection(self, collection_id: str) -> bool:
        """删除集合"""
        self._ensure_initialized()
        result = self.store.delete_collection(collection_id)
        self.events.emit(
            event_type="deleted",
            target_type="collection",
            target_id=collection_id,
            description="删除集合",
        )
        return result

    # ===== 文档操作 =====

    def add_documents(
        self,
        collection_id: str,
        texts: List[str],
        created_by: str = "system",
    ) -> IngestResult:
        """添加文档（自动嵌入）"""
        self._ensure_initialized()
        result = self._ingest.ingest_texts(texts, collection_id, created_by=created_by)
        if result.documents_added > 0:
            # 更新集合的 item_count
            col = self.store.get_collection(collection_id)
            if col:
                current_count = col.get("item_count", 0)
                self.store.update_collection(
                    collection_id, item_count=current_count + result.documents_added
                )
        self.events.emit(
            event_type="created",
            target_type="document",
            target_id=collection_id,
            actor_type=created_by,
            description=f"添加 {result.documents_added} 个文档",
        )
        return result

    def get_document(self, document_id: str) -> Optional[dict]:
        """获取文档"""
        self._ensure_initialized()
        return self.store.get_document(document_id)

    def update_document(self, document_id: str, **kwargs) -> Optional[dict]:
        """更新文档"""
        self._ensure_initialized()
        result = self.store.update_document(document_id, **kwargs)
        if result:
            self.events.emit(
                event_type="updated",
                target_type="document",
                target_id=document_id,
                description=f"更新文档字段: {list(kwargs.keys())}",
            )
        return result

    def delete_documents(self, filter_expr: str) -> bool:
        """删除文档"""
        self._ensure_initialized()
        result = self.store.delete_documents(filter_expr)
        self.events.emit(
            event_type="deleted",
            target_type="document",
            description=f"删除文档: {filter_expr}",
        )
        return result

    # ===== 数据摄入 =====

    def ingest_file(
        self,
        file_path: str,
        collection_id: Optional[str] = None,
        created_by: str = "system",
        **kwargs,
    ) -> IngestResult:
        """导入文件（自动检测类型）"""
        self._ensure_initialized()
        result = self._ingest.ingest_file(
            file_path, collection_id, created_by=created_by, **kwargs
        )
        self.events.emit(
            event_type="created",
            target_type="document",
            target_id=result.collection_id,
            actor_type=created_by,
            description=f"导入文件: {file_path} ({result.documents_added} 个文档)",
        )
        return result

    def ingest_directory(
        self,
        dir_path: str,
        collection_id: Optional[str] = None,
        recursive: bool = True,
        patterns: Optional[List[str]] = None,
        created_by: str = "system",
    ) -> IngestResult:
        """批量导入目录"""
        self._ensure_initialized()
        result = self._ingest.ingest_directory(
            dir_path, collection_id, recursive=recursive,
            patterns=patterns, created_by=created_by,
        )
        self.events.emit(
            event_type="created",
            target_type="document",
            target_id=result.collection_id,
            actor_type=created_by,
            description=f"导入目录: {dir_path} ({result.documents_added} 个文档)",
        )
        return result

    # ===== 搜索 =====

    def search(
        self,
        query: str,
        search_type: str = "hybrid",
        collection_id: Optional[str] = None,
        limit: int = 10,
        filter_expr: Optional[str] = None,
        **kwargs,
    ) -> List[dict]:
        """
        统一搜索接口

        Args:
            query: 搜索查询
            search_type: 搜索类型 (vector, text, hybrid, multimodal)
            collection_id: 限定集合
            limit: 返回数量
            filter_expr: 过滤表达式
        """
        self._ensure_initialized()

        if search_type == "vector":
            results = self._search.vector_search(
                query, collection_id=collection_id, limit=limit, filter_expr=filter_expr
            )
        elif search_type == "text":
            results = self._search.text_search(
                query, collection_id=collection_id, limit=limit, filter_expr=filter_expr
            )
        elif search_type == "hybrid":
            reranker = kwargs.get("reranker", "rrf")
            results = self._search.hybrid_search(
                query, collection_id=collection_id, limit=limit,
                filter_expr=filter_expr, reranker=reranker,
            )
        elif search_type == "multimodal":
            query_type = kwargs.get("query_type", "text")
            target_type = kwargs.get("target_type")
            results = self._search.multimodal_search(
                query, query_type=query_type, target_type=target_type,
                collection_id=collection_id, limit=limit,
            )
        else:
            results = self._search.hybrid_search(
                query, collection_id=collection_id, limit=limit, filter_expr=filter_expr
            )

        # 记录搜索事件
        self.events.emit(
            event_type="searched",
            target_type="document",
            description=f"搜索 [{search_type}]: {query[:100]}",
        )

        return results

    def find_similar(
        self,
        document_id: str,
        limit: int = 10,
        collection_id: Optional[str] = None,
    ) -> List[dict]:
        """相似文档发现"""
        self._ensure_initialized()
        return self._search.find_similar(document_id, limit=limit, collection_id=collection_id)

    # ===== 关系管理 =====

    def create_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str = "related_to",
        description: Optional[str] = None,
        confidence: float = 1.0,
        is_ai_inferred: bool = False,
        metadata_json: Optional[str] = None,
    ) -> dict:
        """创建关系"""
        self._ensure_initialized()
        relation_id = str(uuid.uuid4())
        result = self.store.create_relation(
            id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            description=description,
            confidence=confidence,
            is_ai_inferred=is_ai_inferred,
            metadata_json=metadata_json,
        )
        self.events.emit(
            event_type="created",
            target_type="relation",
            target_id=relation_id,
            description=f"创建关系: {source_id} --[{relation_type}]--> {target_id}",
        )
        return result

    def get_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation_type: Optional[str] = None,
    ) -> List[dict]:
        """查询关系"""
        self._ensure_initialized()
        return self.store.get_relations(
            source_id=source_id, target_id=target_id, relation_type=relation_type
        )

    def delete_relation(self, relation_id: str) -> bool:
        """删除关系"""
        self._ensure_initialized()
        result = self.store.delete_relation(relation_id)
        self.events.emit(
            event_type="deleted",
            target_type="relation",
            target_id=relation_id,
            description="删除关系",
        )
        return result

    # ===== Agent 记忆 =====

    def store_memory(
        self,
        agent_id: str,
        content: str,
        memory_type: str = "semantic",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata_json: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> dict:
        """存储 Agent 记忆"""
        self._ensure_initialized()
        vector = self.embedding_manager.embed_text(content)
        now = now_iso()

        memory_dict = {
            "id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "memory_type": memory_type,
            "content": content,
            "vector": vector,
            "importance": importance,
            "access_count": 0,
            "last_accessed": now,
            "expires_at": expires_at,
            "tags": tags or [],
            "metadata_json": metadata_json,
            "created_at": now,
        }

        self.store.store_memory(memory_dict)
        self.events.emit(
            event_type="created",
            target_type="memory",
            target_id=memory_dict["id"],
            description=f"Agent {agent_id} 存储记忆: {content[:50]}",
        )
        return memory_dict

    def recall_memories(
        self,
        agent_id: str,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """检索 Agent 记忆"""
        self._ensure_initialized()
        return self._search.recall_memories(
            agent_id, query, memory_type=memory_type, limit=limit
        )

    def forget_memories(
        self,
        agent_id: str,
        memory_type: Optional[str] = None,
    ) -> bool:
        """遗忘 Agent 记忆"""
        self._ensure_initialized()
        result = self.store.delete_memories(agent_id, memory_type=memory_type)
        self.events.emit(
            event_type="deleted",
            target_type="memory",
            description=f"Agent {agent_id} 遗忘记忆 (type={memory_type})",
        )
        return result

    def get_memory_stats(self, agent_id: str) -> dict:
        """获取 Agent 记忆统计"""
        self._ensure_initialized()
        memories = self.store.get_memories(agent_id)

        if not memories:
            return MemoryStats(agent_id=agent_id).model_dump()

        by_type = {}
        total_importance = 0.0
        timestamps = []

        for m in memories:
            mt = m.get("memory_type", "unknown")
            by_type[mt] = by_type.get(mt, 0) + 1
            total_importance += m.get("importance", 0.0)
            if m.get("created_at"):
                timestamps.append(m["created_at"])

        timestamps.sort()

        return MemoryStats(
            agent_id=agent_id,
            total_memories=len(memories),
            by_type=by_type,
            avg_importance=total_importance / len(memories) if memories else 0.0,
            oldest_memory=timestamps[0] if timestamps else None,
            newest_memory=timestamps[-1] if timestamps else None,
        ).model_dump()

    # ===== 分层投影 (Layered Projection) =====
    #
    # 核心原则：Agent 不需要一次看全部元数据。
    # L0 → L1 → L2 → L3 逐层钻入，每层 token 开销可控。
    #
    # L0: 位面索引     ~200 tokens   "有哪些域？"
    # L1: 位面概览     ~500 tokens   "这个域有什么实体？"
    # L2: 实体详情     ~200 tokens   "这个实体有什么字段？"
    # L3: 关系图       ~300 tokens   "这些域怎么连？"

    def projection_l0(self, limit: int = 20, offset: int = 0) -> dict:
        """
        L0: 位面索引 — 系统全局概览

        返回集合列表（分页），附带下一步建议。
        适合冷启动时 Agent 了解"这个系统里有什么"。

        Args:
            limit: 最多返回多少位面（默认 20）
            offset: 跳过前 N 个
        """
        self._ensure_initialized()
        stats = self.store.table_stats()
        all_collections = self.store.list_collections()
        total = len(all_collections)
        page = all_collections[offset:offset + limit]

        planes = []
        top_plane = None
        top_count = -1
        for c in page:
            count = c.get("item_count", 0)
            # 如果 item_count 为 0 但实际有文档，用实际数量
            if count == 0:
                actual_docs = self.store.list_documents(
                    collection_id=c.get("id", ""), limit=1
                )
                if actual_docs:
                    all_docs = self.store.list_documents(
                        collection_id=c.get("id", ""), limit=10000
                    )
                    count = len(all_docs)
                    # 顺便修复存储中的 item_count
                    self.store.update_collection(c.get("id", ""), item_count=count)
            entry = {
                "id": c.get("id", ""),
                "name": c.get("name", ""),
                "description": (c.get("description") or "")[:60],
                "type": c.get("collection_type", ""),
                "item_count": count,
            }
            planes.append(entry)
            if count > top_count:
                top_count = count
                top_plane = entry

        return {
            "level": "L0",
            "summary": {
                "total_planes": total,
                "total_entities": stats.get("documents", 0),
                "total_relations": stats.get("relations", 0),
            },
            "pagination": {
                "offset": offset,
                "limit": limit,
                "returned": len(planes),
                "has_more": (offset + limit) < total,
            },
            "planes": planes,
            "hint": {
                "next": f"projection_l1('{top_plane['id']}')" if top_plane else None,
                "reason": f"位面 '{top_plane['name']}' 有最多实体 ({top_count})" if top_plane else None,
            },
        }

    def projection_l1(
        self,
        collection_id: str,
        limit: int = 30,
        offset: int = 0,
    ) -> dict:
        """
        L1: 位面概览 — 单个位面的元信息 + 实体列表（分页）

        Args:
            collection_id: 集合 ID
            limit: 最多返回多少实体（默认 30）
            offset: 跳过前 N 个
        """
        self._ensure_initialized()

        col = self.store.get_collection(collection_id)
        if not col:
            return {"ok": False, "level": "L1", "error": f"Collection not found: {collection_id}"}

        all_docs = self.store.list_documents(collection_id=collection_id, limit=1000)
        total = len(all_docs)
        page = all_docs[offset:offset + limit]

        entities = []
        for d in page:
            content = d.get("content", "")
            # 结构化摘要：提取 entity name + type（前两个 | 段）
            if "|" in content:
                parts = [p.strip() for p in content.split("|")]
                label = " | ".join(parts[:2])[:100]  # name + type
            else:
                label = content[:100]
            entities.append({
                "id": d.get("id", ""),
                "label": label,
                "content_type": d.get("content_type", ""),
            })

        # 该位面涉及的关系
        rels_out = self.store.get_relations(source_id=collection_id)
        rels_in = self.store.get_relations(target_id=collection_id)
        rel_summaries = []
        seen = set()
        for r in rels_out + rels_in:
            rid = r.get("id", "")
            if rid in seen:
                continue
            seen.add(rid)
            rel_summaries.append({
                "type": r.get("relation_type", ""),
                "description": (r.get("description") or "")[:60],
                "confidence": r.get("confidence", 0),
            })

        return {
            "ok": True,
            "level": "L1",
            "plane": {
                "id": col.get("id", ""),
                "name": col.get("name", ""),
                "description": col.get("description", ""),
                "type": col.get("collection_type", ""),
                "status": col.get("status", ""),
                "tags": col.get("tags", []),
            },
            "pagination": {
                "total": total,
                "offset": offset,
                "limit": limit,
                "returned": len(entities),
                "has_more": (offset + limit) < total,
            },
            "entities": entities,
            "relations": rel_summaries,
        }

    def projection_l2(self, document_id: str) -> dict:
        """
        L2: 实体详情 — 单个实体的完整信息

        返回完整内容和解析后的元数据。
        """
        self._ensure_initialized()

        doc = self.store.get_document(document_id)
        if not doc:
            return {"ok": False, "level": "L2", "error": f"Document not found: {document_id}"}

        # 解析 metadata_json
        metadata = None
        raw_meta = doc.get("metadata_json")
        if raw_meta:
            try:
                import json as _json
                metadata = _json.loads(raw_meta)
            except (ValueError, TypeError):
                metadata = raw_meta  # 解析失败保留原始字符串

        return {
            "ok": True,
            "level": "L2",
            "entity": {
                "id": doc.get("id", ""),
                "collection_id": doc.get("collection_id", ""),
                "content": doc.get("content", ""),
                "content_type": doc.get("content_type", ""),
                "tags": doc.get("tags", []),
                "source_uri": doc.get("source_uri"),
                "metadata": metadata,
                "created_at": doc.get("created_at", ""),
            },
        }

    def projection_l3(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """
        L3: 关系图 — 实体/位面间的关系（分页，双向过滤）

        Args:
            source_id: 按源过滤
            target_id: 按目标过滤
            relation_type: 按关系类型过滤
            limit: 最多返回多少条
        """
        self._ensure_initialized()

        # 收集关系（支持 source 和 target 双向过滤）
        if source_id and target_id:
            rels_s = self.store.get_relations(source_id=source_id, relation_type=relation_type)
            relations = [r for r in rels_s if r.get("target_id") == target_id]
        elif source_id:
            relations = self.store.get_relations(source_id=source_id, relation_type=relation_type)
        elif target_id:
            relations = self.store.get_relations(target_id=target_id, relation_type=relation_type)
        else:
            relations = self.store.get_relations(relation_type=relation_type)

        total = len(relations)
        page = relations[:limit]

        # 检测悬空关系：收集所有涉及的 ID，批量验证存在性
        endpoint_ids = set()
        for r in page:
            endpoint_ids.add(r.get("source_id", ""))
            endpoint_ids.add(r.get("target_id", ""))
        existing_ids = set()
        for eid in endpoint_ids:
            if eid and (self.store.get_collection(eid) or self.store.get_document(eid)):
                existing_ids.add(eid)

        edges = []
        dangling_count = 0
        for r in page:
            src = r.get("source_id", "")
            tgt = r.get("target_id", "")
            is_dangling = (src not in existing_ids) or (tgt not in existing_ids)
            if is_dangling:
                dangling_count += 1
            edges.append({
                "id": r.get("id", ""),
                "source_id": src,
                "target_id": tgt,
                "type": r.get("relation_type", ""),
                "description": (r.get("description") or "")[:80],
                "confidence": r.get("confidence", 0),
                "is_ai_inferred": r.get("is_ai_inferred", False),
                "dangling": is_dangling,
            })

        return {
            "ok": True,
            "level": "L3",
            "filter": {
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": relation_type,
            },
            "pagination": {
                "total": total,
                "returned": len(edges),
                "limit": limit,
                "has_more": total > limit,
            },
            "dangling_count": dangling_count,
            "relations": edges,
        }

    # ===== 系统 =====

    def get_world_model(self) -> dict:
        """获取世界模型（全量，大规模数据下请用 projection_l0-l3 替代）"""
        self._ensure_initialized()
        return self.store.get_world_model()

    def get_events(
        self,
        target_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """查询事件历史"""
        self._ensure_initialized()
        return self.events.get_history(
            target_id=target_id, event_type=event_type, limit=limit
        )

    def optimize(self) -> dict:
        """数据库优化"""
        self._ensure_initialized()
        result = self.store.optimize()
        self.events.emit(
            event_type="updated",
            target_type="system",
            description="数据库优化完成",
        )
        return result

    def get_stats(self) -> dict:
        """获取系统统计"""
        self._ensure_initialized()
        return self.store.table_stats()
