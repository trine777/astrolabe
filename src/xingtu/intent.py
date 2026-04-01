"""
星图 XingTu - 意图翻译器

将人类自然语言意图转化为结构化的宇宙目标。
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from .embeddings import EmbeddingManager
from .models import GoalStatus, UniverseGoal, now_iso


class IntentTranslator:
    """
    意图翻译器

    职责：
    1. 接收人类自然语言意图
    2. 调用 AI 理解意图
    3. 生成结构化的 UniverseGoal
    4. 描述预期的宇宙状态
    """

    def __init__(
        self,
        embedding_manager: Optional[EmbeddingManager] = None,
        ai_provider: str = "openai",
        model: str = "gpt-4",
    ):
        """
        初始化意图翻译器

        Args:
            embedding_manager: 嵌入管理器
            ai_provider: AI 提供商
            model: 使用的模型
        """
        self.embedding_manager = embedding_manager or EmbeddingManager()
        self.ai_provider = ai_provider
        self.model = model

    async def translate(
        self,
        intent_text: str,
        world_context: Dict[str, Any],
        user_id: str = "user",
    ) -> UniverseGoal:
        """
        翻译意图为结构化目标

        Args:
            intent_text: 用户意图文本
            world_context: 当前世界模型上下文
            user_id: 用户 ID

        Returns:
            UniverseGoal: 结构化的宇宙目标
        """
        # 1. 生成意图向量
        intent_vector = await self._embed_intent(intent_text)

        # 2. 调用 AI 理解意图
        understanding = await self._understand_intent(intent_text, world_context)

        # 3. 构建 UniverseGoal
        goal = UniverseGoal(
            id=str(uuid.uuid4()),
            intent_text=intent_text,
            intent_vector=intent_vector,
            status=GoalStatus.pending.value,
            expected_collections=json.dumps(understanding.get("expected_collections", [])),
            expected_documents=json.dumps(understanding.get("expected_documents", [])),
            expected_relations=json.dumps(understanding.get("expected_relations", [])),
            confidence=understanding.get("confidence", 0.0),
            reasoning=understanding.get("reasoning"),
            created_by=user_id,
            created_at=now_iso(),
            updated_at=now_iso(),
        )

        return goal

    async def _embed_intent(self, intent_text: str) -> List[float]:
        """生成意图的嵌入向量"""
        return self.embedding_manager.embed_text(intent_text)

    async def _understand_intent(
        self, intent_text: str, world_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用 AI 理解意图

        Args:
            intent_text: 意图文本
            world_context: 世界模型上下文

        Returns:
            理解结果，包含：
            - expected_collections: 预期的集合状态
            - expected_documents: 预期的文档状态
            - expected_relations: 预期的关系状态
            - confidence: 置信度
            - reasoning: 推理过程
        """
        # 构建 AI 提示词
        prompt = self._build_understanding_prompt(intent_text, world_context)

        # 调用 AI（这里需要实际的 AI 调用实现）
        # 暂时返回模拟结果
        understanding = await self._call_ai(prompt)

        return understanding

    def _build_understanding_prompt(
        self, intent_text: str, world_context: Dict[str, Any]
    ) -> str:
        """
        构建 AI 理解提示词

        Args:
            intent_text: 意图文本
            world_context: 世界模型上下文

        Returns:
            提示词字符串
        """
        # 提取世界模型关键信息
        collections_summary = self._summarize_collections(
            world_context.get("collections", [])
        )

        prompt = f"""你是星图（XingTu）的意图理解 Agent。

当前世界模型状态：
- 集合数量: {world_context.get('collection_count', 0)}
- 文档数量: {world_context.get('document_count', 0)}
- 关系数量: {world_context.get('relation_count', 0)}

现有集合：
{collections_summary}

用户意图：
"{intent_text}"

请分析用户意图，并输出 JSON 格式的预期宇宙状态：

{{
  "confidence": 0.0-1.0,  // 理解置信度
  "reasoning": "...",  // 推理过程
  "expected_collections": [  // 预期的集合状态
    {{
      "action": "create|update|delete",
      "id": "collection_id",  // 如果是 update/delete
      "name": "集合名称",
      "description": "集合描述",
      "collection_type": "documents|images|structured|...",
      "tags": ["tag1", "tag2"]
    }}
  ],
  "expected_documents": [  // 预期的文档状态
    {{
      "action": "create|update|delete",
      "collection_id": "所属集合ID",
      "content": "文档内容",
      "content_type": "text|image|...",
      "tags": ["tag1"]
    }}
  ],
  "expected_relations": [  // 预期的关系状态
    {{
      "action": "create|delete",
      "source_id": "源ID",
      "target_id": "目标ID",
      "relation_type": "references|similar_to|...",
      "description": "关系描述"
    }}
  ]
}}

注意：
1. 只其他文字
2. 如果意图不明确，confidence 设低一些
3. action 必须是 create/update/delete 之一
4. 尽量复用现有集合，避免重复创建
"""
        return prompt

    def _summarize_collections(self, collections: List[Dict[str, Any]]) -> str:
        """总结现有集合信息"""
        if not collections:
            return "（无）"

        lines = []
        for col in collections[:10]:  # 最多显示 10 个
            lines.append(
                f"- {col.get('name', 'Unknown')} ({col.get('collection_type', 'unknown')}): "
                f"{col.get('item_count', 0)} 项"
            )

        if len(collections) > 10:
            lines.append(f"... 还有 {len(collections) - 10} 个集合")

        return "\n".join(lines)

    async def _call_ai(self, prompt: str) -> Dict[str, Any]:
        """
        调用 AI API

        TODO: 实现实际的 AI 调用
        目前返回模拟结果
        """
        # 这里应该调用 OpenAI/Claude 等 API
        # 暂时返回一个示例结果
        return {
            "confidence": 0.85,
            "reasoning": "用户意图明确，需要创建新的数据集合",
            "expected_collections": [
                {
                    "action": "create",
                    "name": "示例集合",
                    "description": "根据用户意图创建的集合",
                    "collection_type": "documents",
               "tags": ["auto-created"],
                }
            ],
            "expected_documents": [],
            "expected_relations": [],
        }


class IntentValidator:
    """
    意图验证器

    验证生成的 UniverseGoal 是否合理
    """

    def validate(self, goal: UniverseGoal) -> tuple[bool, Optional[str]]:
        """
        验证目标

        Returns:
            (is_valid, error_message)
        """
        # 检查置信度
        if goal.confidence < 0.3:
            return False, "意图理解置信度过低，请提供更明确的描述"

        # 检查是否有预期状态（解析 JSON 字符串）
        try:
            expected_collections = json.loads(goal.expected_collections)
            expected_documents = json.loads(goal.expected_documents)
            expected_relations = json.loads(goal.expected_relations)
        except json.JSONDecodeError:
            return False, "预期状态 JSON 格式错误"

        has_expectations = (
            expected_collections
            or expected_documents
            or expected_relations
        )
        if not has_expectations:
            return False, "无法从意图中提取出具体的操作目标"

        # 检查 action 字段
        for col in expected_collections:
            if col.get("action") not in ["create", "update", "delete"]:
                return False, f"集合操作类型无效: {col.get('action')}"

        for doc in expected_documents:
            if doc.get("action") not in ["create", "update", "delete"]:
                return False, f"文档操作类型无效: {doc.get('action')}"

        for rel in expected_relations:
            if rel.get("action") not in ["create", "delete"]:
                return False, f"关系操作类型无效: {rel.get('action')}"

        return True, None
