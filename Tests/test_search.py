"""
星图 XingTu - 搜索引擎测试

测试 ChixinheSearch 的各种搜索功能。
"""

from __future__ import annotations

import uuid

import pytest

from xingtu.store import XingkongzuoStore
from xingtu.embeddings import EmbeddingManager
from xingtu.search import ChixinheSearch
from xingtu.config import EmbeddingConfig
from xingtu.models import now_iso


@pytest.fixture
def store(tmp_path):
    """创建临时存储实例"""
    s = XingkongzuoStore(str(tmp_path / "test_db"))
    s.initialize()
    return s


@pytest.fixture
def embedding_manager():
    """创建零向量嵌入管理器（测试用）"""
    config = EmbeddingConfig(provider="none", dimension=1536)
    em = EmbeddingManager(config)
    em.initialize()
    return em


@pytest.fixture
def search(store, embedding_manager):
    """创建搜索引擎实例"""
    return ChixinheSearch(store, embedding_manager)


@pytest.fixture
def populated_store(store):
    """填充测试数据的存储"""
    cid = str(uuid.uuid4())
    store.create_collection(id=cid, name="搜索测试集")

    now = now_iso()
    docs = []
    for i in range(5):
        # 使用略有不同的向量以便测试向量搜索
        vector = [0.0] * 1536
        vector[0] = float(i) * 0.1
        docs.append({
            "id": f"doc-{i}",
            "collection_id": cid,
            "content": f"这是第 {i} 个测试文档，包含关键词 alpha beta gamma",
            "vector": vector,
            "content_type": "text",
            "source_uri": None,
            "tags": [f"tag-{i}"],
            "metadata_json": None,
            "created_at": now,
            "updated_at": now,
            "created_by": "system",
        })
    store.add_documents(docs)
    return store, cid


class TestVectorSearch:
    """向量搜索测试"""

    def test_vector_search_basic(self, search, populated_store):
        store, cid = populated_store
        results = search.vector_search("测试查询", collection_id=cid, limit=3)
        assert isinstance(results, list)
        assert len(results) <= 3
        for r in results:
            assert "id" in r
            assert "content" in r
            assert "score" in r

    def test_vector_search_empty(self, search, store):
        # 搜索空表不应报错
        results = search.vector_search("查询")
        assert isinstance(results, list)


class TestFindSimilar:
    """相似文档发现测试"""

    def test_find_similar(self, search, populated_store):
        store, cid = populated_store
        results = search.find_similar("doc-0", limit=3)
        assert isinstance(results, list)
        # 不应包含源文档本身
        ids = [r["id"] for r in results]
        assert "doc-0" not in ids

    def test_find_similar_nonexistent(self, search, store):
        results = search.find_similar("nonexistent-doc")
        assert results == []


class TestAgentMemoryRecall:
    """Agent 记忆检索测试"""

    def test_recall_memories(self, search, store, embedding_manager):
        # 存储一些记忆
        now = now_iso()
        for i in range(3):
            vector = [0.0] * 1536
            vector[0] = float(i) * 0.1
            store.store_memory({
                "id": f"mem-{i}",
                "agent_id": "test-agent",
                "memory_type": "semantic",
                "content": f"记忆内容 {i}",
                "vector": vector,
                "importance": 0.5 + i * 0.1,
                "access_count": 0,
                "last_accessed": now,
                "expires_at": None,
                "tags": [],
                "metadata_json": None,
                "created_at": now,
            })

        results = search.recall_memories("test-agent", "查询记忆")
        assert isinstance(results, list)
        assert len(results) <= 10

    def test_recall_memories_empty(self, search, store):
        results = search.recall_memories("nonexistent-agent", "查询")
        assert isinstance(results, list)


class TestSearchResults:
    """搜索结果格式测试"""

    def test_result_format(self, search, populated_store):
        store, cid = populated_store
        results = search.vector_search("测试", collection_id=cid, limit=1)
        if results:
            r = results[0]
            assert "id" in r
            assert "content" in r
            assert "score" in r
            assert "content_type" in r
            assert isinstance(r["score"], float)
