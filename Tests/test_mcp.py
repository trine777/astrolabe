"""
星图 XingTu - MCP Server 测试

测试 MCP 工具函数的基本功能。
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid

import pytest


@pytest.fixture(autouse=True)
def setup_env(tmp_path):
    """设置测试环境变量"""
    os.environ["XINGTU_DB_PATH"] = str(tmp_path / "test_mcp_db")
    os.environ["XINGTU_EMBEDDING_PROVIDER"] = "none"
    yield
    os.environ.pop("XINGTU_DB_PATH", None)
    os.environ.pop("XINGTU_EMBEDDING_PROVIDER", None)


@pytest.fixture(autouse=True)
def reset_service():
    """每个测试重置全局服务实例"""
    import xingtu_mcp.server as srv
    srv._service = None
    yield
    srv._service = None


class TestCollectionTools:
    """集合管理工具测试"""

    def test_create_collection(self):
        from xingtu_mcp.server import xingtu_create_collection
        result = json.loads(xingtu_create_collection(name="测试集合", description="测试描述"))
        assert result["name"] == "测试集合"
        assert "id" in result

    def test_list_collections(self):
        from xingtu_mcp.server import xingtu_create_collection, xingtu_list_collections
        xingtu_create_collection(name="集合A")
        result = json.loads(xingtu_list_collections())
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_get_collection(self):
        from xingtu_mcp.server import xingtu_create_collection, xingtu_get_collection
        created = json.loads(xingtu_create_collection(name="查询集合"))
        cid = created["id"]
        result = json.loads(xingtu_get_collection(cid))
        assert result["name"] == "查询集合"

    def test_get_collection_not_found(self):
        from xingtu_mcp.server import xingtu_get_collection
        result = json.loads(xingtu_get_collection("nonexistent"))
        assert "error" in result

    def test_update_collection(self):
        from xingtu_mcp.server import xingtu_create_collection, xingtu_update_collection
        created = json.loads(xingtu_create_collection(name="原始名"))
        cid = created["id"]
        result = json.loads(xingtu_update_collection(cid, name="新名称"))
        assert result["name"] == "新名称"

    def test_delete_collection(self):
        from xingtu_mcp.server import (
            xingtu_create_collection, xingtu_delete_collection, xingtu_get_collection
        )
        created = json.loads(xingtu_create_collection(name="待删除"))
        cid = created["id"]
        result = json.loads(xingtu_delete_collection(cid))
        assert result["status"] == "deleted"


class TestDocumentTools:
    """文档操作工具测试"""

    def test_add_documents(self):
        from xingtu_mcp.server import xingtu_create_collection, xingtu_add_documents
        created = json.loads(xingtu_create_collection(name="文档集"))
        cid = created["id"]
        result = json.loads(xingtu_add_documents(cid, ["文本一", "文本二"]))
        assert result["documents_added"] == 2


class TestSearchTools:
    """搜索工具测试"""

    def _setup_data(self):
        from xingtu_mcp.server import xingtu_create_collection, xingtu_add_documents
        created = json.loads(xingtu_create_collection(name="搜索集"))
        cid = created["id"]
        xingtu_add_documents(cid, ["量子计算的最新进展", "深度学习在医疗领域的应用"])
        return cid

    def test_vector_search(self):
        cid = self._setup_data()
        from xingtu_mcp.server import xingtu_vector_search
        result = json.loads(xingtu_vector_search("量子计算", collection_id=cid))
        assert isinstance(result, list)

    def test_hybrid_search(self):
        cid = self._setup_data()
        from xingtu_mcp.server import xingtu_hybrid_search
        result = json.loads(xingtu_hybrid_search("深度学习", collection_id=cid))
        assert isinstance(result, list)


class TestMemoryTools:
    """Agent 记忆工具测试"""

    def test_store_memory(self):
        from xingtu_mcp.server import xingtu_store_memory
        result = json.loads(xingtu_store_memory(
            agent_id="claude", content="用户偏好深色主题",
            memory_type="semantic", importance=0.8,
        ))
        assert "id" in result
        assert result.get("agent_id") == "claude"

    def test_get_memory_stats(self):
        from xingtu_mcp.server import xingtu_store_memory, xingtu_get_memory_stats
        xingtu_store_memory(agent_id="stats-agent", content="记忆内容")
        result = json.loads(xingtu_get_memory_stats("stats-agent"))
        assert result["agent_id"] == "stats-agent"
        assert result["total_memories"] >= 1

    def test_forget_memories(self):
        from xingtu_mcp.server import xingtu_store_memory, xingtu_forget_memories
        xingtu_store_memory(agent_id="forget-agent", content="临时记忆")
        result = json.loads(xingtu_forget_memories("forget-agent"))
        assert result["status"] == "forgotten"


class TestSystemTools:
    """系统工具测试"""

    def test_get_world_model(self):
        from xingtu_mcp.server import xingtu_get_world_model
        result = json.loads(xingtu_get_world_model())
        assert "collections" in result
        assert "collection_count" in result
        assert "document_count" in result

    def test_get_events(self):
        from xingtu_mcp.server import xingtu_create_collection, xingtu_get_events
        xingtu_create_collection(name="事件测试")
        result = json.loads(xingtu_get_events())
        assert isinstance(result, list)

    def test_optimize(self):
        from xingtu_mcp.server import xingtu_optimize
        result = json.loads(xingtu_optimize())
        assert isinstance(result, dict)
