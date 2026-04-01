"""
星图 XingTu - 嵌入管理

管理多种嵌入模型提供商，支持文本、图片、多模态嵌入。
利用 LanceDB 的嵌入注册表系统。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from .config import EmbeddingConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# 零向量维度常量
DEFAULT_DIMENSION = 1536


class EmbeddingManager:
    """
    嵌入函数管理器

    支持多种嵌入提供商：
    - none: 不使用嵌入（零向量占位）
    - openai: OpenAI text-embedding-3-small/large
    - ollama: 本地 Ollama 模型
    - sentence-transformers: HuggingFace 模型
    - open-clip: 多模态嵌入（文本+图片）
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self.dimension = self.config.dimension
        self._text_embedder = None
        self._image_embedder = None
        self._multimodal_embedder = None
        self._initialized = False

    def initialize(self) -> None:
        """初始化嵌入提供商"""
        if self._initialized:
            return

        provider = self.config.provider.lower()

        if provider == "none":
            logger.info("嵌入提供商: none（使用零向量）")
        elif provider == "openai":
            self._setup_openai()
        elif provider == "ollama":
            self._setup_ollama()
        elif provider == "sentence-transformers":
            self._setup_sentence_transformers()
        elif provider == "open-clip":
            self._setup_multimodal()
        else:
            logger.warning(f"未知嵌入提供商: {provider}，使用零向量")

        self._initialized = True

    def _setup_openai(self) -> None:
        """配置 OpenAI 嵌入"""
        try:
            from lancedb.embeddings import get_registry

            registry = get_registry()
            self._text_embedder = registry.get("openai").create(
                name=self.config.model,
                api_key=self.config.api_key,
            )
            self.dimension = self._text_embedder.ndims()
            logger.info(f"OpenAI 嵌入已配置: {self.config.model}, dim={self.dimension}")
        except ImportError:
            logger.error("需要安装 openai: pip install 'xingtu[embeddings-openai]'")
            raise
        except Exception as e:
            logger.error(f"OpenAI 嵌入配置失败: {e}")
            raise

    def _setup_ollama(self) -> None:
        """配置 Ollama 嵌入"""
        try:
            from lancedb.embeddings import get_registry

            registry = get_registry()
            kwargs = {"name": self.config.model}
            if self.config.base_url:
                kwargs["host"] = self.config.base_url
            self._text_embedder = registry.get("ollama").create(**kwargs)
            self.dimension = self._text_embedder.ndims()
            logger.info(f"Ollama 嵌入已配置: {self.config.model}, dim={self.dimension}")
        except ImportError:
            logger.error("需要安装 ollama: pip install 'xingtu[embeddings-ollama]'")
            raise
        except Exception as e:
            logger.error(f"Ollama 嵌入配置失败: {e}")
            raise

    def _setup_sentence_transformers(self) -> None:
        """配置 Sentence Transformers 嵌入"""
        try:
            from lancedb.embeddings import get_registry

            registry = get_registry()
            self._text_embedder = registry.get("sentence-transformers").create(
                name=self.config.model,
            )
            self.dimension = self._text_embedder.ndims()
            logger.info(
                f"Sentence Transformers 嵌入已配置: {self.config.model}, dim={self.dimension}"
            )
        except ImportError:
            logger.error(
                "需要安装 sentence-transformers: pip install 'xingtu[embeddings-local]'"
            )
            raise
        except Exception as e:
            logger.error(f"Sentence Transformers 嵌入配置失败: {e}")
            raise

    def _setup_multimodal(self) -> None:
        """配置多模态嵌入 (OpenCLIP)"""
        try:
            from lancedb.embeddings import get_registry

            registry = get_registry()
            self._multimodal_embedder = registry.get("open-clip").create(
                name=self.config.model,
            )
            self._text_embedder = self._multimodal_embedder
            self._image_embedder = self._multimodal_embedder
            self.dimension = self._multimodal_embedder.ndims()
            logger.info(f"多模态嵌入已配置: {self.config.model}, dim={self.dimension}")
        except ImportError:
            logger.error(
                "需要安装 open-clip: pip install 'xingtu[embeddings-multimodal]'"
            )
            raise
        except Exception as e:
            logger.error(f"多模态嵌入配置失败: {e}")
            raise

    # ===== 获取嵌入函数 =====

    def get_text_embedder(self):
        """获取文本嵌入函数"""
        self.initialize()
        return self._text_embedder

    def get_image_embedder(self):
        """获取图片嵌入函数"""
        self.initialize()
        return self._image_embedder

    def get_multimodal_embedder(self):
        """获取多模态嵌入函数"""
        self.initialize()
        return self._multimodal_embedder

    # ===== 手动嵌入 =====

    def embed_text(self, text: str) -> List[float]:
        """嵌入单个文本"""
        self.initialize()
        if self._text_embedder is None:
            return self._zero_vector()
        result = self._text_embedder.compute_query_embeddings(text)
        if isinstance(result, list) and len(result) > 0:
            vec = result[0]
            return vec if isinstance(vec, list) else vec.tolist()
        return self._zero_vector()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文本"""
        self.initialize()
        if self._text_embedder is None:
            return [self._zero_vector() for _ in texts]
        results = self._text_embedder.compute_source_embeddings(texts)
        output = []
        for vec in results:
            if isinstance(vec, list):
                output.append(vec)
            else:
                output.append(vec.tolist())
        return output

    def embed_image(self, image_path: str) -> List[float]:
        """嵌入图片"""
        self.initialize()
        if self._image_embedder is None:
            logger.warning("图片嵌入未配置，返回零向量")
            return self._zero_vector()
        try:
            result = self._image_embedder.compute_source_embeddings([image_path])
            if isinstance(result, list) and len(result) > 0:
                vec = result[0]
                return vec if isinstance(vec, list) else vec.tolist()
        except Exception as e:
            logger.error(f"图片嵌入失败: {e}")
        return self._zero_vector()

    def _zero_vector(self) -> List[float]:
        """返回零向量（当没有嵌入提供商时使用）"""
        return [0.0] * self.dimension

    @property
    def is_configured(self) -> bool:
        """是否已配置嵌入提供商"""
        return self.config.provider.lower() != "none"
