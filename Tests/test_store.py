"""
星图 XingTu - 存储层测试

测试 XingkongzuoStore 的 CRUD 操作。
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest

from xingtu.store import XingkongzuoStore
from xingtu.models import now_iso


@pytest.fixture
def store(tmp_path):
    """创建临时存储实例"""
    s = XingkongzuoStore(str(tmp_path / "test_db"))
    s.initialize()
    return s


class TestCollections:
    """集合 CRUD 测试"""

    def test_create_collection(self, store):
        col = store.create_collection(
            id=str(uuid.uuid4()),
            name="测试集合",
            description="这是一个测试集合",
            collection_type="documents",
        )
        assert col["name"] == "测试集合"
        assert col["status"] == "draft"
        assert col["collection_type"] == "documents"

    def test_get_collection(self, store):
        cid = str(uuid.uuid4())
        store.create_collection(id=cid, name="查询测试")
        result = store.get_collection(cid)
        assert result is not None
        assert result["id"] == cid
        assert result["name"] == "查询测试"

    def test_get_collection_not_found(self, store):
        result = store.get_collection("nonexistent-id")
        assert result is None

    def test_list_collections(self, store):
        store.create_collection(id=str(uuid.uuid4()), name="集合A", collection_type="documents")
        store.create_collection(id=str(uuid.uuid4()), name="集合B", collection_type="images")
        results = store.list_collections()
        assert len(results) >= 2

    def test_list_collections_filter_type(self, store):
        store.create_collection(id=str(uuid.uuid4()), name="文档集", collection_type="documents")
        store.create_collection(id=str(uuid.uuid4()), name="图片集", collection_type="images")
        results = store.list_collections(collection_type="images")
        names = [r["name"] for r in results]
        assert "图片集" in names

    def test_update_collection(self, store):
        cid = str(uuid.uuid4())
        store.create_collection(id=cid, name="原始名称")
        updated = store.update_collection(cid, name="新名称", status="confirmed")
        assert updated is not None
        assert updated["name"] == "新名称"
        assert updated["status"] == "confirmed"

    def test_delete_collection(self, store):
        cid = str(uuid.uuid4())
        store.create_collection(id=cid, name="待删除")
        store.delete_collection(cid)
        result = store.get_collection(cid)
        assert result is None


class TestDocuments:
    """文档 CRUD 测试"""

    def test_add_and_get_document(self, store):
        doc_id = str(uuid.uuid4())
        cid = str(uuid.uuid4())
        store.create_collection(id=cid, name="文档测试集")
        docs = [{
            "id": doc_id,
            "collection_id": cid,
            "content": "这是测试文档内容",
            "vector": [0.0] * 1536,
            "content_type": "text",
            "source_uri": None,
            "tags": [],
            "metadata_json": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "created_by": "system",
        }]
        count = store.add_documents(docs)
        assert count == 1

        result = store.get_document(doc_id)
        assert result is not None
        assert result["content"] == "这是测试文档内容"

    def test_add_empty_documents(self, store):
        count = store.add_documents([])
        assert count == 0

    def test_list_documents(self, store):
        cid = str(uuid.uuid4())
        store.create_collection(id=cid, name="列表测试")
        now = now_iso()
        docs = []
        for i in range(3):
            docs.append({
                "id": str(uuid.uuid4()),
                "collection_id": cid,
                "content": f"文档 {i}",
                "vector": [float(i)] * 1536,
                "content_type": "text",
                "source_uri": None,
                "tags": [],
                "metadata_json": None,
                "created_at": now,
                "updated_at": now,
                "created_by": "system",
            })
        store.add_documents(docs)
        results = store.list_documents(collection_id=cid)
        assert len(results) == 3

    def test_delete_documents(self, store):
        cid = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        store.create_collection(id=cid, name="删除测试")
        store.add_documents([{
            "id": doc_id,
            "collection_id": cid,
            "content": "待删除文档",
            "vector": [0.0] * 1536,
            "content_type": "text",
            "source_uri": None,
            "tags": [],
            "metadata_json": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "created_by": "system",
        }])
        store.delete_documents(f"id = '{doc_id}'")
        result = store.get_document(doc_id)
        assert result is None


class TestRelations:
    """关系 CRUD 测试"""

    def test_create_and_get_relation(self, store):
        rid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        result = store.create_relation(
            id=rid, source_id=sid, target_id=tid,
            relation_type="references", description="测试关系",
        )
        assert result["relation_type"] == "references"

        relations = store.get_relations(source_id=sid)
        assert len(relations) >= 1

    def test_delete_relation(self, store):
        rid = str(uuid.uuid4())
        store.create_relation(
            id=rid, source_id="s1", target_id="t1",
        )
        store.delete_relation(rid)
        relations = store.get_relations(source_id="s1")
        found = [r for r in relations if r.get("id") == rid]
        assert len(found) == 0


class TestEvents:
    """事件操作测试"""

    def test_add_and_get_events(self, store):
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": now_iso(),
            "event_type": "created",
            "target_type": "collection",
            "target_id": "test-target",
            "actor_type": "system",
            "actor_id": None,
            "description": "测试事件",
            "before_snapshot": None,
            "after_snapshot": None,
        }
        store.add_event(event)
        events = store.get_events(target_id="test-target")
        assert len(events) >= 1


class TestAgentMemory:
    """Agent 记忆测试"""

    def test_store_and_get_memory(self, store):
        memory = {
            "id": str(uuid.uuid4()),
            "agent_id": "test-agent",
            "memory_type": "semantic",
            "content": "用户喜欢深色主题",
            "vector": [0.1] * 1536,
            "importance": 0.8,
            "access_count": 0,
            "last_accessed": now_iso(),
            "expires_at": None,
            "tags": ["preference"],
            "metadata_json": None,
            "created_at": now_iso(),
        }
        store.store_memory(memory)
        memories = store.get_memories("test-agent")
        assert len(memories) >= 1

    def test_delete_memories(self, store):
        memory = {
            "id": str(uuid.uuid4()),
            "agent_id": "forget-agent",
            "memory_type": "working",
            "content": "临时记忆",
            "vector": [0.0] * 1536,
            "importance": 0.3,
            "access_count": 0,
            "last_accessed": now_iso(),
            "expires_at": None,
            "tags": [],
            "metadata_json": None,
            "created_at": now_iso(),
        }
        store.store_memory(memory)
        store.delete_memories("forget-agent")
        memories = store.get_memories("forget-agent")
        assert len(memories) == 0


class TestWorldModel:
    """世界模型测试"""

    def test_get_world_model(self, store):
        store.create_collection(id=str(uuid.uuid4()), name="世界模型测试")
        wm = store.get_world_model()
        assert "collections" in wm
        assert "collection_count" in wm
        assert "document_count" in wm
        assert wm["collection_count"] >= 1


class TestMaintenance:
    """维护操作测试"""

    def test_table_stats(self, store):
        stats = store.table_stats()
        assert "collections" in stats
        assert "documents" in stats
        assert "relations" in stats
        assert "events" in stats
        assert "agent_memories" in stats

    def test_optimize(self, store):
        result = store.optimize()
        assert isinstance(result, dict)
