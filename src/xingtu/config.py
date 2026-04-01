"""
星图 XingTu - 配置管理

管理星图系统的所有配置项，支持环境变量和配置文件。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    """嵌入模型配置"""

    provider: str = Field(
        default="none",
        description="嵌入提供商: none | openai | ollama | sentence-transformers | open-clip",
    )
    model: str = Field(
        default="text-embedding-3-small",
        description="嵌入模型名称",
    )
    dimension: int = Field(
        default=1536,
        description="嵌入向量维度",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API 密钥（OpenAI 等）",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="API 基础 URL（Ollama 等）",
    )


class StoreConfig(BaseModel):
    """存储配置"""

    db_path: str = Field(
        default="~/.xingtu/data",
        description="LanceDB 数据库路径",
    )

    @property
    def resolved_path(self) -> Path:
        return Path(self.db_path).expanduser()


class SearchConfig(BaseModel):
    """搜索配置"""

    default_limit: int = Field(default=10, description="默认返回结果数")
    default_distance_type: str = Field(default="cosine", description="默认距离类型")
    default_reranker: str = Field(default="rrf", description="默认重排序器")
    fts_enabled: bool = Field(default=True, description="是否启用全文搜索")


class MCPConfig(BaseModel):
    """MCP Server 配置"""

    server_name: str = Field(default="xingtu", description="MCP 服务器名称")
    server_version: str = Field(default="2.0.0", description="MCP 服务器版本")


class XingTuConfig(BaseModel):
    """星图全局配置"""

    store: StoreConfig = Field(default_factory=StoreConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    @classmethod
    def from_env(cls) -> XingTuConfig:
        """从环境变量加载配置"""
        config = cls()

        # 存储路径
        if db_path := os.environ.get("XINGTU_DB_PATH"):
            config.store.db_path = db_path

        # 嵌入配置
        if provider := os.environ.get("XINGTU_EMBEDDING_PROVIDER"):
            config.embedding.provider = provider
        if model := os.environ.get("XINGTU_EMBEDDING_MODEL"):
            config.embedding.model = model
        if dim := os.environ.get("XINGTU_EMBEDDING_DIMENSION"):
            config.embedding.dimension = int(dim)
        if api_key := os.environ.get("OPENAI_API_KEY"):
            config.embedding.api_key = api_key
        if base_url := os.environ.get("XINGTU_EMBEDDING_BASE_URL"):
            config.embedding.base_url = base_url

        return config

    @classmethod
    def default(cls) -> XingTuConfig:
        """返回默认配置"""
        return cls.from_env()
