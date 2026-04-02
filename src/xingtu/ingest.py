"""
星图 XingTu - 数据摄入（语界枢）

多模态数据导入引擎，支持文本、CSV、JSON、PDF、图片等格式。
"""

from __future__ import annotations

import csv
import json
import logging
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from .models import IngestResult, now_iso

if TYPE_CHECKING:
    from .embeddings import EmbeddingManager
    from .store import XingkongzuoStore

logger = logging.getLogger(__name__)


class YujieshuIngest:
    """
    语界枢 - 多模态数据摄入

    支持多种数据格式的导入：
    - 纯文本
    - CSV 文件
    - JSON 文件
    - PDF 文件（需要 pymupdf）
    - 图片文件
    - 目录批量导入
    """

    def __init__(self, store: XingkongzuoStore, embedding_manager: EmbeddingManager):
        self.store = store
        self.embedding_manager = embedding_manager

    def ingest_text(
        self,
        text: str,
        collection_id: str,
        content_type: str = "text",
        source_uri: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata_json: Optional[str] = None,
        created_by: str = "system",
    ) -> dict:
        """导入单个文本"""
        vector = self.embedding_manager.embed_text(text)
        now = now_iso()

        doc = {
            "id": str(uuid.uuid4()),
            "collection_id": collection_id,
            "content": text,
            "vector": vector,
            "content_type": content_type,
            "source_uri": source_uri,
            "tags": tags or [],
            "metadata_json": metadata_json,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
        }

        self.store.add_documents([doc])
        return doc

    def ingest_texts(
        self,
        texts: List[str],
        collection_id: str,
        created_by: str = "system",
    ) -> IngestResult:
        """批量导入文本"""
        vectors = self.embedding_manager.embed_texts(texts)
        now = now_iso()
        docs = []
        errors = []

        for i, (text, vector) in enumerate(zip(texts, vectors)):
            try:
                doc = {
                    "id": str(uuid.uuid4()),
                    "collection_id": collection_id,
                    "content": text,
                    "vector": vector,
                    "content_type": "text",
                    "source_uri": None,
                    "tags": [],
                    "metadata_json": None,
                    "created_at": now,
                    "updated_at": now,
                    "created_by": created_by,
                }
                docs.append(doc)
            except Exception as e:
                errors.append(f"Text {i}: {e}")

        if docs:
            self.store.add_documents(docs)

        return IngestResult(
            collection_id=collection_id,
            documents_added=len(docs),
            documents_failed=len(errors),
            document_ids=[d["id"] for d in docs],
            errors=errors,
        )

    def ingest_csv(
        self,
        file_path: str,
        collection_id: Optional[str] = None,
        text_columns: Optional[List[str]] = None,
        created_by: str = "system",
    ) -> IngestResult:
        """
        导入 CSV 文件

        每行生成一个文档。如果指定 text_columns，只用这些列的内容；
        否则将所有列拼接为文本。
        """
        path = Path(file_path)
        if not path.exists():
            return IngestResult(
                collection_id=collection_id or "",
                errors=[f"File not found: {file_path}"],
            )

        # 自动创建集合
        if collection_id is None:
            collection_id = str(uuid.uuid4())
            self.store.create_collection(
                id=collection_id,
                name=path.stem,
                collection_type="structured",
                created_by=created_by,
            )

        docs = []
        errors = []

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                return IngestResult(
                    collection_id=collection_id,
                    errors=["CSV file is empty"],
                )

            # 确定文本列
            columns = text_columns or list(rows[0].keys())

            # 生成文本内容
            texts = []
            for row in rows:
                parts = []
                for col in columns:
                    val = row.get(col, "")
                    if val:
                        parts.append(f"{col}: {val}")
                texts.append("; ".join(parts))

            # 批量嵌入
            vectors = self.embedding_manager.embed_texts(texts)
            now = now_iso()

            for i, (text, vector, row) in enumerate(zip(texts, vectors, rows)):
                try:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "collection_id": collection_id,
                        "content": text,
                        "vector": vector,
                        "content_type": "structured",
                        "source_uri": str(path.absolute()),
                        "tags": [],
                        "metadata_json": json.dumps(row, ensure_ascii=False),
                        "created_at": now,
                        "updated_at": now,
                        "created_by": created_by,
                    }
                    docs.append(doc)
                except Exception as e:
                    errors.append(f"Row {i}: {e}")

            if docs:
                self.store.add_documents(docs)

            # 更新集合计数
            self.store.update_collection(collection_id, item_count=len(docs))

        except Exception as e:
            errors.append(f"CSV parsing error: {e}")

        return IngestResult(
            collection_id=collection_id,
            documents_added=len(docs),
            documents_failed=len(errors),
            document_ids=[d["id"] for d in docs],
            errors=errors,
            source=str(path),
        )

    def ingest_json(
        self,
        file_path: str,
        collection_id: Optional[str] = None,
        content_field: Optional[str] = None,
        created_by: str = "system",
    ) -> IngestResult:
        """
        导入 JSON 文件

        支持 JSON 数组或单个对象。
        如果指定 content_field，用该字段作为文本内容；
        否则将整个对象序列化为文本。
        """
        path = Path(file_path)
        if not path.exists():
            return IngestResult(
                collection_id=collection_id or "",
                errors=[f"File not found: {file_path}"],
            )

        if collection_id is None:
            collection_id = str(uuid.uuid4())
            self.store.create_collection(
                id=collection_id,
                name=path.stem,
                collection_type="documents",
                created_by=created_by,
            )

        docs = []
        errors = []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                data = [data]

            if not isinstance(data, list):
                return IngestResult(
                    collection_id=collection_id,
                    errors=["JSON must be an array or object"],
                )

            texts = []
            for item in data:
                if content_field and content_field in item:
                    texts.append(str(item[content_field]))
                else:
                    texts.append(json.dumps(item, ensure_ascii=False))

            vectors = self.embedding_manager.embed_texts(texts)
            now = now_iso()

            for i, (text, vector, item) in enumerate(zip(texts, vectors, data)):
                try:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "collection_id": collection_id,
                        "content": text,
                        "vector": vector,
                        "content_type": "text",
                        "source_uri": str(path.absolute()),
                        "tags": [],
                        "metadata_json": json.dumps(item, ensure_ascii=False),
                        "created_at": now,
                        "updated_at": now,
                        "created_by": created_by,
                    }
                    docs.append(doc)
                except Exception as e:
                    errors.append(f"Item {i}: {e}")

            if docs:
                self.store.add_documents(docs)

            self.store.update_collection(collection_id, item_count=len(docs))

        except Exception as e:
            errors.append(f"JSON parsing error: {e}")

        return IngestResult(
            collection_id=collection_id,
            documents_added=len(docs),
            documents_failed=len(errors),
            document_ids=[d["id"] for d in docs],
            errors=errors,
            source=str(path),
        )

    def ingest_pdf(
        self,
        file_path: str,
        collection_id: Optional[str] = None,
        chunk_size: int = 512,
        created_by: str = "system",
    ) -> IngestResult:
        """
        导入 PDF 文件

        将 PDF 按页或按 chunk_size 分割为多个文档。
        需要 pymupdf: pip install 'xingtu[pdf]'
        """
        path = Path(file_path)
        if not path.exists():
            return IngestResult(
                collection_id=collection_id or "",
                errors=[f"File not found: {file_path}"],
            )

        try:
            import fitz  # pymupdf
        except ImportError:
            return IngestResult(
                collection_id=collection_id or "",
                errors=["pymupdf not installed. Run: pip install 'xingtu[pdf]'"],
            )

        if collection_id is None:
            collection_id = str(uuid.uuid4())
            self.store.create_collection(
                id=collection_id,
                name=path.stem,
                collection_type="documents",
                created_by=created_by,
            )

        docs = []
        errors = []

        try:
            pdf = fitz.open(str(path))
            chunks = []

            for page_num in range(len(pdf)):
                page = pdf[page_num]
                text = page.get_text()
                if not text.strip():
                    continue

                # 按 chunk_size 分割
                words = text.split()
                current_chunk = []
                current_len = 0

                for word in words:
                    current_chunk.append(word)
                    current_len += len(word) + 1
                    if current_len >= chunk_size:
                        chunks.append({
                            "text": " ".join(current_chunk),
                            "page": page_num + 1,
                        })
                        current_chunk = []
                        current_len = 0

                if current_chunk:
                    chunks.append({
                        "text": " ".join(current_chunk),
                        "page": page_num + 1,
                    })

            pdf.close()

            if not chunks:
                return IngestResult(
                    collection_id=collection_id,
                    errors=["PDF contains no extractable text"],
                )

            texts = [c["text"] for c in chunks]
            vectors = self.embedding_manager.embed_texts(texts)
            now = now_iso()

            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                try:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "collection_id": collection_id,
                        "content": chunk["text"],
                        "vector": vector,
                        "content_type": "text",
                        "source_uri": str(path.absolute()),
                        "tags": [],
                        "metadata_json": json.dumps({
                            "page": chunk["page"],
                            "chunk_index": i,
                            "source_file": path.name,
                        }),
                        "created_at": now,
                        "updated_at": now,
                        "created_by": created_by,
                    }
                    docs.append(doc)
                except Exception as e:
                    errors.append(f"Chunk {i}: {e}")

            if docs:
                self.store.add_documents(docs)

            self.store.update_collection(collection_id, item_count=len(docs))

        except Exception as e:
            errors.append(f"PDF processing error: {e}")

        return IngestResult(
            collection_id=collection_id,
            documents_added=len(docs),
            documents_failed=len(errors),
            document_ids=[d["id"] for d in docs],
            errors=errors,
            source=str(path),
        )

    def ingest_image(
        self,
        image_path: str,
        collection_id: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: str = "system",
    ) -> dict:
        """导入单张图片"""
        path = Path(image_path)
        content = description or f"Image: {path.name}"
        vector = self.embedding_manager.embed_image(str(path))
        now = now_iso()

        doc = {
            "id": str(uuid.uuid4()),
            "collection_id": collection_id,
            "content": content,
            "vector": vector,
            "content_type": "image",
            "source_uri": str(path.absolute()),
            "tags": tags or [],
            "metadata_json": json.dumps({
                "filename": path.name,
                "extension": path.suffix,
            }),
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
        }

        self.store.add_documents([doc])
        return doc

    def ingest_images(
        self,
        image_dir: str,
        collection_id: str,
        extensions: Optional[List[str]] = None,
        created_by: str = "system",
    ) -> IngestResult:
        """批量导入图片目录"""
        dir_path = Path(image_dir)
        if not dir_path.is_dir():
            return IngestResult(
                collection_id=collection_id,
                errors=[f"Directory not found: {image_dir}"],
            )

        exts = extensions or [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]
        docs = []
        errors = []

        for img_path in sorted(dir_path.iterdir()):
            if img_path.suffix.lower() in exts:
                try:
                    doc = self.ingest_image(
                        str(img_path), collection_id, created_by=created_by
                    )
                    docs.append(doc)
                except Exception as e:
                    errors.append(f"{img_path.name}: {e}")

        self.store.update_collection(collection_id, item_count=len(docs))

        return IngestResult(
            collection_id=collection_id,
            documents_added=len(docs),
            documents_failed=len(errors),
            document_ids=[d["id"] for d in docs],
            errors=errors,
            source=str(dir_path),
        )

    def ingest_file(
        self,
        file_path: str,
        collection_id: Optional[str] = None,
        created_by: str = "system",
        **kwargs,
    ) -> IngestResult:
        """
        通用文件导入（自动检测类型）

        根据文件扩展名自动选择导入方式。
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".csv":
            return self.ingest_csv(file_path, collection_id, created_by=created_by, **kwargs)
        elif suffix == ".json":
            return self.ingest_json(file_path, collection_id, created_by=created_by, **kwargs)
        elif suffix == ".pdf":
            return self.ingest_pdf(file_path, collection_id, created_by=created_by, **kwargs)
        elif suffix in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
            if collection_id is None:
                collection_id = str(uuid.uuid4())
                self.store.create_collection(
                    id=collection_id,
                    name=path.stem,
                    collection_type="images",
                    created_by=created_by,
                )
            doc = self.ingest_image(file_path, collection_id, created_by=created_by)
            return IngestResult(
                collection_id=collection_id,
                documents_added=1,
                document_ids=[doc["id"]],
                source=str(path),
            )
        elif suffix in (".txt", ".md", ".rst"):
            if collection_id is None:
                collection_id = str(uuid.uuid4())
                self.store.create_collection(
                    id=collection_id,
                    name=path.stem,
                    collection_type="documents",
                    created_by=created_by,
                )
            text = path.read_text(encoding="utf-8")
            doc = self.ingest_text(text, collection_id, source_uri=str(path), created_by=created_by)
            self.store.update_collection(collection_id, item_count=1)
            return IngestResult(
                collection_id=collection_id,
                documents_added=1,
                document_ids=[doc["id"]],
                source=str(path),
            )
        else:
            return IngestResult(
                collection_id=collection_id or "",
                errors=[f"Unsupported file type: {suffix}"],
            )

    def ingest_directory(
        self,
        dir_path: str,
        collection_id: Optional[str] = None,
        recursive: bool = True,
        patterns: Optional[List[str]] = None,
        created_by: str = "system",
    ) -> IngestResult:
        """
        批量导入目录

        递归扫描目录中的所有支持文件并导入。
        """
        path = Path(dir_path)
        if not path.is_dir():
            return IngestResult(
                collection_id=collection_id or "",
                errors=[f"Directory not found: {dir_path}"],
            )

        if collection_id is None:
            collection_id = str(uuid.uuid4())
            self.store.create_collection(
                id=collection_id,
                name=path.name,
                collection_type="multimodal",
                created_by=created_by,
            )

        total_added = 0
        total_failed = 0
        all_errors = []
        all_doc_ids = []

        # 收集文件
        if recursive:
            files = list(path.rglob("*"))
        else:
            files = list(path.glob("*"))

        # 过滤模式
        if patterns:
            import fnmatch
            filtered = []
            for f in files:
                for pat in patterns:
                    if fnmatch.fnmatch(f.name, pat):
                        filtered.append(f)
                        break
            files = filtered

        # 只处理文件
        files = [f for f in files if f.is_file()]

        for file in sorted(files):
            try:
                result = self.ingest_file(
                    str(file), collection_id, created_by=created_by
                )
                total_added += result.documents_added
                total_failed += result.documents_failed
                all_errors.extend(result.errors)
                all_doc_ids.extend(result.document_ids)
            except Exception as e:
                total_failed += 1
                all_errors.append(f"{file.name}: {e}")

        self.store.update_collection(collection_id, item_count=total_added)

        return IngestResult(
            collection_id=collection_id,
            documents_added=total_added,
            documents_failed=total_failed,
            document_ids=all_doc_ids,
            errors=all_errors,
            source=str(path),
        )
