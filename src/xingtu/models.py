"""
星图 XingTu - 数据模型

用 LanceDB 的 Pydantic + LanceModel 定义多模态数据模型。
所有模型均为 LanceDB 表的 schema 定义。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from lancedb.pydantic import LanceModel, Vector
from pydantic import BaseModel, Field


# ===== 枚举类型 =====


class CollectionStatus(str, Enum):
    """集合状态"""

    draft = "draft"
    confirmed = "confirmed"
    published = "published"
    archived = "archived"


class CollectionType(str, Enum):
    """集合类型"""

    documents = "documents"  # 文本文档
    images = "images"  # 图片集
    audio = "audio"  # 音频集
    multimodal = "multimodal"  # 混合多模态
    structured = "structured"  # 结构化数据(CSV等)
    knowledge = "knowledge"  # 知识图谱节点


class ContentType(str, Enum):
    """内容类型"""

    text = "text"
    image = "image"
    audio = "audio"
    video = "video"
    structured = "structured"


class RelationType(str, Enum):
    """关系类型"""

    references = "references"
    derived_from = "derived_from"
    similar_to = "similar_to"
    part_of = "part_of"
    contains = "contains"
    related_to = "related_to"


class EventType(str, Enum):
    """事件类型"""

    created = "created"
    updated = "updated"
    deleted = "deleted"
    searched = "searched"
    inferred = "inferred"
    confirmed = "confirmed"
    published = "published"
    archived = "archived"


class ActorType(str, Enum):
    """操作者类型"""

    user = "user"
    ai = "ai"
    system = "system"


class MemoryType(str, Enum):
    """记忆类型"""

    working = "working"  # 工作记忆（短期）
    episodic = "episodic"  # 情景记忆
    semantic = "semantic"  # 语义记忆
    procedural = "procedural"  # 程序记忆


class GoalStatus(str, Enum):
    """目标状态"""

    pending = "pending"  # 待处理
    in_progress = "in_progress"  # 进行中
    completed = "completed"  # 已完成
    failed = "failed"  # 失败
    cancelled = "cancelled"  # 已取消


class DeltaType(str, Enum):
    """差分类型"""

    create_collection = "create_collection"  # 创建集合
    update_collection = "update_collection"  # 更新集合
    delete_collection = "delete_collection"  # 删除集合
    add_document = "add_document"  # 添加文档
    update_document = "update_document"  # 更新文档
    delete_document = "delete_document"  # 删除文档
    create_relation = "create_relation"  # 创建关系
    delete_relation = "delete_relation"  # 删除关系
    infer_metadata = "infer_metadata"  # 推断元数据


# ===== 辅助函数 =====


def now_iso() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat()


# ===== LanceDB 表模型 =====


class Collection(LanceModel):
    """
    数据集合 - 星图中的一等公民

    对应 LanceDB 表: collections
    """

    id: str = Field(description="集合唯一标识")
    name: str = Field(description="集合名称")
    description: Optional[str] = Field(default=None, description="集合描述")
    collection_type: str = Field(
        default=CollectionType.documents.value, description="集合类型"
    )
    status: str = Field(default=CollectionStatus.draft.value, description="集合状态")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    item_count: int = Field(default=0, description="项目数量")
    created_at: str = Field(default_factory=now_iso, description="创建时间")
    updated_at: str = Field(default_factory=now_iso, description="更新时间")
    created_by: str = Field(default="system", description="创建者类型")
    metadata_json: Optional[str] = Field(default=None, description="扩展元数据 JSON")


class Document(LanceModel):
    """
    多模态文档 - 星图存储的基本单元

    对应 LanceDB 表: documents
    支持向量搜索和全文检索。
    """

    id: str = Field(description="文档唯一标识")
    collection_id: str = Field(description="所属集合 ID")
    content: str = Field(description="文本内容/描述")
    vector: Vector(1536) = Field(description="文本嵌入向量")  # type: ignore[valid-type]
    content_type: str = Field(default=ContentType.text.value, description="内容类型")
    source_uri: Optional[str] = Field(default=None, description="原始文件路径/URL")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    metadata_json: Optional[str] = Field(default=None, description="灵活的元数据 JSON")
    created_at: str = Field(default_factory=now_iso, description="创建时间")
    updated_at: str = Field(default_factory=now_iso, description="更新时间")
    created_by: str = Field(default="system", description="创建者类型")


class Relation(LanceModel):
    """
    数据关系 - 连接不同集合/文档

    对应 LanceDB 表: relations
    """

    id: str = Field(description="关系唯一标识")
    source_id: str = Field(description="源文档/集合 ID")
    target_id: str = Field(description="目标文档/集合 ID")
    relation_type: str = Field(
        default=RelationType.related_to.value, description="关系类型"
    )
    description: Optional[str] = Field(default=None, description="关系描述")
    confidence: float = Field(default=1.0, description="置信度 0-1")
    is_ai_inferred: bool = Field(default=False, description="是否 AI 推断")
    is_confirmed: bool = Field(default=False, description="是否已确认")
    metadata_json: Optional[str] = Field(default=None, description="扩展元数据 JSON")
    created_at: str = Field(default_factory=now_iso, description="创建时间")


class Event(LanceModel):
    """
    变更事件 - 影澜轩的审计流

    对应 LanceDB 表: events
    """

    id: str = Field(description="事件唯一标识")
    timestamp: str = Field(default_factory=now_iso, description="事件时间戳")
    event_type: str = Field(description="事件类型")
    target_type: str = Field(description="目标类型: collection | document | relation")
    target_id: Optional[str] = Field(default=None, description="目标 ID")
    actor_type: str = Field(default=ActorType.system.value, description="操作者类型")
    actor_id: Optional[str] = Field(default=None, description="操作者 ID")
    description: Optional[str] = Field(default=None, description="事件描述")
    before_snapshot: Optional[str] = Field(default=None, description="变更前快照 JSON")
    after_snapshot: Optional[str] = Field(default=None, description="变更后快照 JSON")


class AgentMemory(LanceModel):
    """
    Agent 记忆 - Agent 的工作记忆和长期记忆

    对应 LanceDB 表: agent_memories
    """

    id: str = Field(description="记忆唯一标识")
    agent_id: str = Field(description="Agent ID")
    memory_type: str = Field(
        default=MemoryType.semantic.value, description="记忆类型"
    )
    content: str = Field(description="记忆内容")
    vector: Vector(1536) = Field(description="内容嵌入向量")  # type: ignore[valid-type]
    importance: float = Field(default=0.5, description="重要性评分 0-1")
    access_count: int = Field(default=0, description="访问次数")
    last_accessed: str = Field(default_factory=now_iso, description="最后访问时间")
    expires_at: Optional[str] = Field(default=None, description="过期时间")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    metadata_json: Optional[str] = Field(default=None, description="扩展元数据 JSON")
    created_at: str = Field(default_factory=now_iso, description="创建时间")


class UniverseGoal(LanceModel):
    """
    宇宙目标 - 人类意图转化的结构化目标

    对应 LanceDB 表: universe_goals
    记录用户意图及其对应的预期宇宙状态
    """

    id: str = Field(description="目标唯一标识")
    intent_text: str = Field(description="原始意图文本")
    intent_vector: Vector(384) = Field(description="意图嵌入向量")  # type: ignore[valid-type]
    status: str = Field(default=GoalStatus.pending.value, description="目标状态")

    # 预期宇宙状态（存储为 JSON 字符串）
    expected_collections: str = Field(
        default="[]", description="预期的集合状态 JSON"
    )
    expected_documents: str = Field(
        default="[]", description="预期的文档状态 JSON"
    )
    expected_relations: str = Field(
        default="[]", description="预期的关系状态 JSON"
    )

    # 元信息
    confidence: float = Field(default=0.0, description="意图理解置信度 0-1")
    reasoning: Optional[str] = Field(default=None, description="AI 推理过程")
    created_by: str = Field(default="user", description="创建者")
    created_at: str = Field(default_factory=now_iso, description="创建时间")
    updated_at: str = Field(default_factory=now_iso, description="更新时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
    metadata_json: Optional[str] = Field(default=None, description="扩展元数据 JSON")


class UniverseDelta(LanceModel):
    """
    宇宙差分 - 预期状态与实际状态的差异

    对应 LanceDB 表: universe_deltas
    差分即行动指南，每个差分对应一个或多个行技执行
    """

    id: str = Field(description="差分唯一标识")
    goal_id: str = Field(description="关联的目标 ID")
    delta_type: str = Field(description="差分类型")

    # 差分内容
    target_type: str = Field(
        description="目标类型: collection | document | relation"
    )
    target_id: Optional[str] = Field(default=None, description="目标对象 ID（如已存在）")
    expected_state: str = Field(description="预期状态 JSON")
    actual_state: Optional[str] = Field(default=None, description="实际状态 JSON")
    diff_details: str = Field(description="差分详情 JSON")

    # 执行信息
    priority: int = Field(default=5, description="优先级 1-10，10 最高")
    xingji_id: Optional[str] = Field(default=None, description="对应的行技 ID")
    xingji_params: Optional[str] = Field(default=None, description="行技参数 JSON")

    # 状态
    is_executed: bool = Field(default=False, description="是否已执行")
    execution_result: Optional[str] = Field(default=None, description="执行结果 JSON")
    error_message: Optional[str] = Field(default=None, description="错误信息")

    # 时间
    created_at: str = Field(default_factory=now_iso, description="创建时间")
    executed_at: Optional[str] = Field(default=None, description="执行时间")
    metadata_json: Optional[str] = Field(default=None, description="扩展元数据 JSON")


# ===== 非 LanceDB 辅助模型（用于 API 响应等）=====


class SearchResult(BaseModel):
    """搜索结果"""

    id: str
    content: str
    score: float = Field(description="相关性分数")
    collection_id: Optional[str] = None
    content_type: str = "text"
    source_uri: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[str] = None


class IngestResult(BaseModel):
    """数据摄入结果"""

    collection_id: str
    documents_added: int = 0
    documents_updated: int = 0
    documents_failed: int = 0
    document_ids: List[str] = Field(default_factory=list, description="成功写入的文档 ID 列表")
    errors: List[str] = Field(default_factory=list)
    source: Optional[str] = None


class WorldModel(BaseModel):
    """世界模型 - 星图的完整数据视图"""

    collections: List[dict] = Field(default_factory=list)
    collection_count: int = 0
    document_count: int = 0
    relation_count: int = 0
    agent_count: int = 0
    memory_count: int = 0
    recent_events: List[dict] = Field(default_factory=list)


class TrustVerdict(BaseModel):
    """信任评估结果"""

    item_id: str
    item_type: str = Field(description="document | collection | unknown")
    trust_score: float = Field(description="综合信任分 0-1")
    confidence: float = Field(description="判定可靠度 0-1")
    flags: List[str] = Field(default_factory=list, description="标记列表")
    reasoning: str = Field(default="", description="判定理由")
    dimensions: dict = Field(default_factory=dict, description="各维度分数")


class MemoryStats(BaseModel):
    """Agent 记忆统计"""

    agent_id: str
    total_memories: int = 0
    by_type: dict = Field(default_factory=dict)
    avg_importance: float = 0.0
    oldest_memory: Optional[str] = None
    newest_memory: Optional[str] = None
