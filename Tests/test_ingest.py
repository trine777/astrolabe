"""
星图 XingTu - 数据摄入测试

测试 YujieshuIngest 的各种数据导入功能。
"""

from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path

import pytest

from xingtu.store import XingkongzuoStore
from xingtu.embeddings import EmbeddingManager
from xingtu.ingest import YujieshuIngest
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
def ingest(store, embedding_manager):
    """创建摄入引擎实例"""
    return YujieshuIngest(store, embedding_manager)


class TestTextIngest:
    """文本导入测试"""

    def test_ingest_single_text(self, ingest, store):
        cid = str(uuid.uuid4())
        store.create_collection(id=cid, name="文本测试")
        doc = ingest.ingest_text("这是一段测试文本", cid)
        assert doc["content"] == "这是一段测试文本"
        assert doc["collection_id"] == cid
        assert len(doc["vector"]) == 1536

    def test_ingest_multiple_texts(self, ingest, store):
        cid = str(uuid.uuid4())
        store.create_collection(id=cid, name="批量文本测试")
        result = ingest.ingest_texts(
            ["文本一", "文本二", "文本三"], cid
        )
        assert result.documents_added == 3
        assert result.documents_failed == 0


class TestCSVIngest:
    """CSV 导入测试"""

    def test_ingest_csv(self, ingest, store, tmp_path):
        # 创建测试 CSV
        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "age", "city"])
            writer.writeheader()
            writer.writerow({"name": "Alice", "age": "30", "city": "Beijing"})
            writer.writerow({"name": "Bob", "age": "25", "city": "Shanghai"})

        result = ingest.ingest_csv(str(csv_path))
        assert result.documents_added == 2
        assert result.documents_failed == 0
        assert result.collection_id  # 自动创建了集合

    def test_ingest_csv_with_collection(self, ingest, store, tmp_path):
        cid = str(uuid.uuid4())
        store.create_collection(id=cid, name="CSV测试集")

        csv_path = tmp_path / "test2.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["product", "price"])
            writer.writeheader()
            writer.writerow({"product": "苹果", "price": "5.0"})

        result = ingest.ingest_csv(str(csv_path), collection_id=cid)
        assert result.collection_id == cid
        assert result.documents_added == 1

    def test_ingest_csv_not_found(self, ingest):
        result = ingest.ingest_csv("/nonexistent/file.csv")
        assert len(result.errors) > 0


class TestJSONIngest:
    """JSON 导入测试"""

    def test_ingest_json_array(self, ingest, tmp_path):
        json_path = tmp_path / "test.json"
        data = [
            {"title": "文章一", "content": "内容一"},
            {"title": "文章二", "content": "内容二"},
        ]
        json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = ingest.ingest_json(str(json_path), content_field="content")
        assert result.documents_added == 2

    def test_ingest_json_object(self, ingest, tmp_path):
        json_path = tmp_path / "single.json"
        data = {"name": "测试", "value": 42}
        json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = ingest.ingest_json(str(json_path))
        assert result.documents_added == 1

    def test_ingest_json_not_found(self, ingest):
        result = ingest.ingest_json("/nonexistent/file.json")
        assert len(result.errors) > 0


class TestFileIngest:
    """通用文件导入测试"""

    def test_ingest_txt_file(self, ingest, tmp_path):
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("这是一个纯文本文件的内容", encoding="utf-8")

        result = ingest.ingest_file(str(txt_path))
        assert result.documents_added == 1

    def test_ingest_unsupported_file(self, ingest, tmp_path):
        bin_path = tmp_path / "test.xyz"
        bin_path.write_bytes(b"binary data")

        result = ingest.ingest_file(str(bin_path))
        assert len(result.errors) > 0

    def test_ingest_csv_via_file(self, ingest, tmp_path):
        csv_path = tmp_path / "auto.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["x", "y"])
            writer.writeheader()
            writer.writerow({"x": "1", "y": "2"})

        result = ingest.ingest_file(str(csv_path))
        assert result.documents_added == 1


class TestDirectoryIngest:
    """目录导入测试"""

    def test_ingest_directory(self, ingest, tmp_path):
        # 创建测试文件
        (tmp_path / "a.txt").write_text("文件A", encoding="utf-8")
        (tmp_path / "b.txt").write_text("文件B", encoding="utf-8")
        (tmp_path / "c.bin").write_bytes(b"binary")  # 不支持的格式

        result = ingest.ingest_directory(str(tmp_path))
        assert result.documents_added >= 2

    def test_ingest_directory_not_found(self, ingest):
        result = ingest.ingest_directory("/nonexistent/dir")
        assert len(result.errors) > 0

    def test_ingest_directory_with_patterns(self, ingest, tmp_path):
        (tmp_path / "data.txt").write_text("文本数据", encoding="utf-8")
        (tmp_path / "image.png").write_bytes(b"fake png")

        result = ingest.ingest_directory(
            str(tmp_path), patterns=["*.txt"]
        )
        assert result.documents_added >= 1
