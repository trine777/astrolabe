"""
星图 XingTu - 搜索引擎（炽心核）

统一的多模态搜索接口，支持向量搜索、全文检索、混合查询。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from .models import SearchResult, now_iso

if TYPE_CHECKING:
    from .embeddings import EmbeddingManager
    from .store import XingkongzuoStore

logger = logging.getLogger(__name__)


class ChixinheSearch:
    """
    炽心核 - 搜索与决策引擎

    提供多种搜索模式：
    - 向量搜索（语义检索）
    - 全文搜索（关键词检索）
    - 混合搜索（向量 + 全文）
    - 多模态搜索（文搜图、图搜文等）
    - 相似文档发现
    - Agent 记忆检索
    """

    def __init__(self, store: XingkongzuoStore, embedding_manager: EmbeddingManager):
        self.store = store
        self.embedding_manager = embedding_manager

    def vector_search(
        self,
        query: str,
        collection_id: Optional[str] = None,
        limit: int = 10,
        filter_expr: Optional[str] = None,
        distance_type: str = "cosine",
    ) -> List[dict]:
        """向量语义搜索"""
        table = self.store.get_table("documents")
        query_vector = self.embedding_manager.embed_text(query)

        search = table.search(query_vector, vector_column_name="vector")
        search = search.metric(distance_type)

        conditions = []
        if collection_id:
            conditions.append(f"collection_id = '{collection_id}'")
        if filter_expr:
            conditions.append(filter_expr)
        if conditions:
            search = search.where(" AND ".join(conditions), prefilter=True)

        results = search.limit(limit).to_list()
        return self._format_results(results, score_field="_distance", invert_score=True)

    def text_search(
        self,
        query: str,
        collection_id: Optional[str] = None,
        limit: int = 10,
        filter_expr: Optional[str] = None,
    ) -> List[dict]:
        """全文关键词搜索"""
        table = self.store.get_table("documents")

        # Create FTS index if not exists (idempotent)
        try:
            table.create_fts_index("content", replace=False)
        except Exception:
            pass  # Index already exists

        search = table.search(query, query_type="fts")

        conditions = []
        if collection_id:
            conditions.append(f"collection_id = '{collection_id}'")
        if filter_expr:
            conditions.append(filter_expr)
        if conditions:
            search = search.where(" AND ".join(conditions), prefilter=True)

        results = search.limit(limit).to_list()
        return self._format_results(results, score_field="_score", invert_score=False)

    def hybrid_search(
        self,
        query: str,
        collection_id: Optional[str] = None,
        limit: int = 10,
        filter_expr: Optional[str] = None,
        reranker: str = "rrf",
    ) -> List[dict]:
        """混合搜索（向量 + 全文）"""
        table = self.store.get_table("documents")
        query_vector = self.embedding_manager.embed_text(query)

        # Ensure FTS index exists
        try:
            table.create_fts_index("content", replace=False)
        except Exception:
            pass

        search = table.search(query, query_type="hybrid", vector=query_vector)

        conditions = []
        if collection_id:
            conditions.append(f"collection_id = '{collection_id}'")
        if filter_expr:
            conditions.append(filter_expr)
        if conditions:
            search = search.where(" AND ".join(conditions), prefilter=True)

        # Apply reranker
        if reranker == "rrf":
            from lancedb.rerankers import RRFReranker
            search = search.rerank(reranker=RRFReranker())
        elif reranker == "linear":
            from lancedb.rerankers import LinearCombinationReranker
            search = search.rerank(reranker=LinearCombinationReranker())

        results = search.limit(limit).to_list()
        return self._format_results(results, score_field="_relevance_score", invert_score=False)

    def multimodal_search(
        self,
        query,
        query_type: str = "text",
        target_type: Optional[str] = None,
        collection_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """多模态搜索（文搜图、图搜文等）"""
        if query_type == "text":
            query_vector = self.embedding_manager.embed_text(query)
        elif query_type == "image":
            query_vector = self.embedding_manager.embed_image(query)
        else:
            query_vector = self.embedding_manager.embed_text(str(query))

        table = self.store.get_table("documents")
        search = table.search(query_vector, vector_column_name="vector")

        conditions = []
        if target_type:
            conditions.append(f"content_type = '{target_type}'")
        if collection_id:
            conditions.append(f"collection_id = '{collection_id}'")
        if conditions:
            search = search.where(" AND ".join(conditions), prefilter=True)

        results = search.limit(limit).to_list()
        return self._format_results(results, score_field="_distance", invert_score=True)

    def find_similar(
        self,
        document_id: str,
        limit: int = 10,
        collection_id: Optional[str] = None,
    ) -> List[dict]:
        """相似文档发现"""
        doc = self.store.get_document(document_id)
        if not doc:
            return []

        vector = doc.get("vector")
        if vector is None:
            return []

        table = self.store.get_table("documents")
        search = table.search(vector, vector_column_name="vector")

        # Exclude the source document itself
        conditions = [f"id != '{document_id}'"]
        if collection_id:
            conditions.append(f"collection_id = '{collection_id}'")
        search = search.where(" AND ".join(conditions), prefilter=True)

        results = search.limit(limit).to_list()
        return self._format_results(results, score_field="_distance", invert_score=True)

    def recall_memories(
        self,
        agent_id: str,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """Agent 记忆检索"""
        table = self.store.get_table("agent_memories")
        query_vector = self.embedding_manager.embed_text(query)

        search = table.search(query_vector, vector_column_name="vector")

        conditions = [f"agent_id = '{agent_id}'"]
        if memory_type:
            conditions.append(f"memory_type = '{memory_type}'")
        search = search.where(" AND ".join(conditions), prefilter=True)

        results = search.limit(limit).to_list()

        # Update access count for recalled memories
        mem_table = self.store.get_table("agent_memories")
        for r in results:
            try:
                mem_id = r.get("id")
                if mem_id:
                    mem_table.delete(f"id = '{mem_id}'")
                    r["access_count"] = r.get("access_count", 0) + 1
                    r["last_accessed"] = now_iso()
                    clean = {k: v for k, v in r.items() if not k.startswith("_")}
                    mem_table.add([clean])
            except Exception as e:
                logger.warning(f"Failed to update memory access count: {e}")

        return self._format_results(results, score_field="_distance", invert_score=True)

    def _format_results(
        self,
        results: List[dict],
        score_field: str = "_distance",
        invert_score: bool = False,
    ) -> List[dict]:
        """Format search results into a standard structure"""
        formatted = []
        for r in results:
            score = r.get(score_field, 0.0)
            if score is None:
                score = 0.0
            if invert_score and score != 0:
                score = 1.0 / (1.0 + score)  # Convert distance to similarity

            formatted.append(SearchResult(
                id=r.get("id", ""),
                content=r.get("content", ""),
                score=float(score),
                collection_id=r.get("collection_id"),
                content_type=r.get("content_type", "text"),
                source_uri=r.get("source_uri"),
                tags=r.get("tags"),
                metadata_json=r.get("metadata_json"),
            ).model_dump())

        # Sort by score descending
        formatted.sort(key=lambda x: x["score"], reverse=True)
        return formatted
