"""
星图 XingTu - 小世界模型

核心协调器：人输入意图 → 小世界模型解析意图 → World Model 自己产生 Δ → Agent 自发行动
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .delta import DeltaGenerator
from .embeddings import EmbeddingManager
from .intent import IntentTranslator, IntentValidator
from .models import GoalStatus, UniverseDelta, UniverseGoal, now_iso
from .store import XingkongzuoStore


class UniverseModel:
    """
    小世界模型 - 主权智能体的核心

    职责：
    1. 接收人类意图
    2. 翻译为结构化目标
    3. 计算差分（Δ = Expected - Actual）
    4. 生成行动计划
    5. 触发行技执行

    核心理念：差分即行动指南
    """

    def __init__(
        self,
        store: XingkongzuoStore,
        intent_translator: Optional[IntentTranslator] = None,
        delta_generator: Optional[DeltaGenerator] = None,
        embedding_manager: Optional[EmbeddingManager] = None,
    ):
        """
        初始化小世界模型

        Args:
            store: 星空座存储
            intent_translator: 意图翻译器
            delta_generator: 差分生成器
        """
        self.store = store
        self.intent_translator = intent_translator or IntentTranslator()
        self.delta_generator = delta_generator or DeltaGenerator()
        self.intent_validator = IntentValidator()
        self.embedding_manager = embedding_manager or EmbeddingManager()

    async def process_intent(
        self,
        intent_text: str,
        user_id: str = "user",
        auto_execute: bool = True,
    ) -> Dict[str, Any]:
        """
        处理人类意图（主入口）

        流程：
        1. 意图翻译 → UniverseGoal
        2. 验证目标
        3. 计算差分 → UniverseDelta[]
        4. 保存目标和差分
        5. （可选）自动执行行技

        Args:
            intent_text: 用户意图文本
            user_id: 用户 ID
            auto_execute: 是否自动执行行技

        Returns:
            处理结果，包含目标、差分、执行状态
        """
        # 1. 获取当前世界模型
        world_context = self.store.get_world_model()

        # 2. 翻译意图
        goal = await self.intent_translator.translate(
            intent_text=intent_text,
            world_context=world_context,
            user_id=user_id,
        )

        # 3. 验证目标
        is_valid, error_msg = self.intent_validator.validate(goal)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg,
                "goal": None,
                "deltas": [],
            }

        # 4. 计算差分
        deltas = await self.delta_generator.generate_deltas(
            goal=goal,
            world_context=world_context,
        )

        # 5. 保存目标和差分
        await self._save_goal(goal)
        await self._save_deltas(deltas)

        # 6. 自动执行（如果启用）
        execution_results = []
        if auto_execute:
            execution_results = await self._execute_deltas(deltas)

        return {
            "success": True,
            "goal": self._goal_to_dict(goal),
            "deltas": [self._delta_to_dict(d) for d in deltas],
            "delta_count": len(deltas),
            "execution_results": execution_results,
            "auto_executed": auto_execute,
        }

    async def get_goal_status(self, goal_id: str) -> Dict[str, Any]:
        """
        获取目标执行状态

        Args:
            goal_id: 目标 ID

        Returns:
            目标状态信息
        """
        goal = await self._load_goal(goal_id)
        if not goal:
            return {"error": "Goal not found"}

        deltas = await self._load_deltas_by_goal(goal_id)

        executed_count = sum(1 for d in deltas if d.is_executed)
        failed_count = sum(1 for d in deltas if d.error_message)

        return {
            "goal_id": goal_id,
            "status": goal.status,
            "intent_text": goal.intent_text,
            "confidence": goal.confidence,
            "total_deltas": len(deltas),
            "executed_deltas": executed_count,
            "failed_deltas": failed_count,
            "progress": executed_count / len(deltas) if deltas else 0.0,
            "deltas": [self._delta_to_dict(d) for d in deltas],
        }

    async def execute_delta(self, delta_id: str) -> Dict[str, Any]:
        """
        手动执行单个差分

        Args:
            delta_id: 差分 ID

        Returns:
            执行结果
        """
        delta = await self._load_delta(delta_id)
        if not delta:
            return {"success": False, "error": "Delta not found"}

        result = await self._execute_single_delta(delta)
        return result

    async def list_pending_goals(self) -> List[Dict[str, Any]]:
        """列出所有待处理的目标"""
        # TODO: 从 store 查询
        return []

    async def list_pending_deltas(self) -> List[Dict[str, Any]]:
        """列出所有待执行的差分"""
        # TODO: 从 store 查询
        return []

    # ===== 私有方法 =====

    async def _save_goal(self, goal: UniverseGoal) -> None:
        """保存目标到存储"""
        goal_dict = goal.model_dump()
        self.store.save_goal(goal_dict)

    async def _save_deltas(self, deltas: List[UniverseDelta]) -> None:
        """保存差分到存储"""
        delta_dicts = [d.model_dump() for d in deltas]
        self.store.save_deltas(delta_dicts)

    async def _load_goal(self, goal_id: str) -> Optional[UniverseGoal]:
        """从存储加载目标"""
        goal_dict = self.store.get_goal(goal_id)
        if not goal_dict:
            return None
        return UniverseGoal(**goal_dict)

    async def _load_delta(self, delta_id: str) -> Optional[UniverseDelta]:
        """从存储加载差分"""
        delta_dict = self.store.get_delta(delta_id)
        if not delta_dict:
            return None
        return UniverseDelta(**delta_dict)

    async def _load_deltas_by_goal(self, goal_id: str) -> List[UniverseDelta]:
        """加载目标的所有差分"""
        delta_dicts = self.store.list_deltas(goal_id=goal_id)
        return [UniverseDelta(**d) for d in delta_dicts]

    async def _execute_deltas(self, deltas: List[UniverseDelta]) -> List[Dict[str, Any]]:
        """
        批量执行差分

        按优先级顺序执行，记录结果
        """
        results = []
        for delta in deltas:
            result = await self._execute_single_delta(delta)
            results.append(result)

            # 如果执行失败且是高优先级，可能需要停止后续执行
            if not result.get("success") and delta.priority >= 8:
                break

        return results

    async def _execute_single_delta(self, delta: UniverseDelta) -> Dict[str, Any]:
        """
        执行单个差分

        根据 delta.xingji_id 调用对应的行技
        """
        try:
            # 解析行技参数
            params = json.loads(delta.xingji_params or "{}")

            # 根据行技 ID 调用对应的方法
            if delta.xingji_id == "xingji.create_collection":
                result = await self._xingji_create_collection(params)
            elif delta.xingji_id == "xingji.update_collection":
                result = await self._xingji_update_collection(params)
            elif delta.xingji_id == "xingji.delete_collection":
                result = await self._xingji_delete_collection(params)
            elif delta.xingji_id == "xingji.add_document":
                result = await self._xingji_add_document(params)
            elif delta.xingji_id == "xingji.create_relation":
                result = await self._xingji_create_relation(params)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown xingji: {delta.xingji_id}",
                }

            # 更新差分状态
            delta.is_executed = True
            delta.execution_result = json.dumps(result)
            if not result.get("success"):
                delta.error_message = result.get("error", "Unknown error")

            await self._update_delta(delta)

            return result

        except Exception as e:
            error_result = {"success": False, "error": str(e)}
            delta.error_message = str(e)
            await self._update_delta(delta)
            return error_result

    async def _update_delta(self, delta: UniverseDelta) -> None:
        """更新差分状态"""
        delta_dict = delta.model_dump()
        self.store.update_delta(delta.id, **delta_dict)

    # ===== 行技实现 =====

    async def _xingji_create_collection(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """行技：创建集合"""
        try:
            import uuid
            collection_id = str(uuid.uuid4())
            result = self.store.create_collection(
                id=collection_id,
                name=params["name"],
                description=params.get("description"),
                collection_type=params.get("collection_type", "documents"),
                tags=params.get("tags", []),
            )
            return {"success": True, "collection_id": collection_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _xingji_update_collection(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """行技：更新集合"""
        try:
            collection_id = params["collection_id"]
            updates = {k: v for k, v in params.get("updates", {}).items()}
            result = self.store.update_collection(collection_id, **updates)
            if result is None:
                return {"success": False, "error": f"Collection not found: {collection_id}"}
            return {"success": True, "collection_id": collection_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _xingji_delete_collection(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """行技：删除集合"""
        try:
            collection_id = params["collection_id"]
            self.store.delete_collection(collection_id)
            return {"success": True, "collection_id": collection_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _xingji_add_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """行技：添加文档"""
        try:
            import uuid as _uuid
            content = params["content"]
            vector = self.embedding_manager.embed_text(content)
            now = now_iso()
            doc = {
                "id": str(_uuid.uuid4()),
                "collection_id": params["collection_id"],
                "content": content,
                "content_type": params.get("content_type", "text"),
                "vector": vector,
                "source_uri": params.get("source_uri"),
                "tags": params.get("tags", []),
                "metadata_json": params.get("metadata_json"),
                "created_at": now,
                "updated_at": now,
                "created_by": params.get("created_by", "system"),
            }
            count = self.store.add_documents([doc])
            return {"success": True, "document_id": doc["id"], "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _xingji_create_relation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """行技：创建关系"""
        try:
            import uuid as _uuid
            relation_id = str(_uuid.uuid4())
            result = self.store.create_relation(
                id=relation_id,
                source_id=params["source_id"],
                target_id=params["target_id"],
                relation_type=params.get("relation_type", "related_to"),
                description=params.get("description"),
            )
            return {"success": True, "relation_id": relation_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===== 辅助方法 =====

    def _goal_to_dict(self, goal: UniverseGoal) -> Dict[str, Any]:
        """将 UniverseGoal 转为字典"""
        return {
            "id": goal.id,
            "intent_text": goal.intent_text,
            "status": goal.status,
            "confidence": goal.confidence,
            "reasoning": goal.reasoning,
            "expected_collections": goal.expected_collections,
            "expected_documents": goal.expected_documents,
            "expected_relations": goal.expected_relations,
            "created_at": goal.created_at,
      }

    def _delta_to_dict(self, delta: UniverseDelta) -> Dict[str, Any]:
        """将 UniverseDelta 转为字典"""
        return {
            "id": delta.id,
            "delta_type": delta.delta_type,
            "target_type": delta.target_type,
            "target_id": delta.target_id,
            "priority": delta.priority,
            "xingji_id": delta.xingji_id,
            "is_executed": delta.is_executed,
            "error_message": delta.error_message,
            "diff_details": json.loads(delta.diff_details) if delta.diff_details else {},
        }
