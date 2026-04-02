"""
星图 XingTu - 差分生成器

计算预期宇宙状态与实际宇宙状态的差异，生成行动指南。
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from .models import DeltaType, UniverseDelta, UniverseGoal, now_iso


class DeltaGenerator:
    """
    差分生成器

    职责：
    1. 接收 UniverseGoal（预期状态）
    2. 获取当前世界模型（实际状态）
    3. 计算差分 Δ = Expected - Actual
    4. 生成 UniverseDelta 列表（行动指南）
    """

    def __init__(self):
        pass

    def generate_deltas(
        self,
        goal: UniverseGoal,
        world_context: Dict[str, Any],
    ) -> List[UniverseDelta]:
        """
        生成差分列表（同步方法）
        """
        deltas: List[UniverseDelta] = []

        expected_collections = json.loads(goal.expected_collections)
        expected_documents = json.loads(goal.expected_documents)
        expected_relations = json.loads(goal.expected_relations)

        # 1. 计算集合差分
        collection_deltas = self._compute_collection_deltas(
            expected_collections, world_context.get("collections", [])
        )
        deltas.extend(collection_deltas)

        # 2. 计算文档差分
        document_deltas = self._compute_document_deltas(
            expected_documents, world_context
        )
        deltas.extend(document_deltas)

        # 3. 计算关系差分
        relation_deltas = self._compute_relation_deltas(
            expected_relations, world_context
        )
        deltas.extend(relation_deltas)

        # 4. 为每个差分关联目标 ID
        for delta in deltas:
            delta.goal_id = goal.id

        # 5. 按优先级排序
        deltas.sort(key=lambda d: d.priority, reverse=True)

        return deltas

    def _compute_collection_deltas(
        self,
        expected_collections: List[Dict[str, Any]],
        actual_collections: List[Dict[str, Any]],
    ) -> List[UniverseDelta]:
        """计算集合差分"""
        deltas: List[UniverseDelta] = []

        for expected in expected_collections:
            action = expected.get("action")

            if action == "create":
                existing = self._find_collection_by_name(
                    expected.get("name"), actual_collections
                )
                if existing:
                    delta = self._create_update_collection_delta(expected, existing)
                else:
                    delta = self._create_create_collection_delta(expected)
                deltas.append(delta)

            elif action == "update":
                target_id = expected.get("id")
                existing = self._find_collection_by_id(target_id, actual_collections)
                if existing:
                    delta = self._create_update_collection_delta(expected, existing)
                    deltas.append(delta)

            elif action == "delete":
                target_id = expected.get("id")
                existing = self._find_collection_by_id(target_id, actual_collections)
                if existing:
                    delta = self._create_delete_collection_delta(existing)
                    deltas.append(delta)

        return deltas

    def _compute_document_deltas(
        self,
        expected_documents: List[Dict[str, Any]],
        world_context: Dict[str, Any],
    ) -> List[UniverseDelta]:
        """计算文档差分"""
        deltas: List[UniverseDelta] = []

        for expected in expected_documents:
            action = expected.get("action")

            if action == "create":
                delta = self._create_add_document_delta(expected)
                deltas.append(delta)

        return deltas

    def _compute_relation_deltas(
        self,
        expected_relations: List[Dict[str, Any]],
        world_context: Dict[str, Any],
    ) -> List[UniverseDelta]:
        """计算关系差分"""
        deltas: List[UniverseDelta] = []

        for expected in expected_relations:
            action = expected.get("action")

            if action == "create":
                delta = self._create_create_relation_delta(expected)
                deltas.append(delta)

        return deltas

    # ===== 差分创建辅助方法 =====

    def _create_create_collection_delta(
        self, expected: Dict[str, Any]
    ) -> UniverseDelta:
        """创建"创建集合"差分"""
        return UniverseDelta(
            id=str(uuid.uuid4()),
            goal_id="",
            delta_type=DeltaType.create_collection.value,
            target_type="collection",
            target_id=None,
            expected_state=json.dumps(expected),
            actual_state=json.dumps({}),
            diff_details=json.dumps({"action": "create", "data": expected}),
            priority=8,
            xingji_id="xingji.create_collection",
            xingji_params=json.dumps(
                {
                    "name": expected.get("name"),
                    "description": expected.get("description"),
                    "collection_type": expected.get("collection_type", "documents"),
                    "tags": expected.get("tags", []),
                }
            ),
            created_at=now_iso(),
        )

    def _create_update_collection_delta(
        self, expected: Dict[str, Any], existing: Dict[str, Any]
    ) -> UniverseDelta:
        """创建"更新集合"差分"""
        diff = self._compute_dict_diff(existing, expected)

        return UniverseDelta(
            id=str(uuid.uuid4()),
            goal_id="",
            delta_type=DeltaType.update_collection.value,
            target_type="collection",
            target_id=existing.get("id"),
            expected_state=json.dumps(expected),
            actual_state=json.dumps(existing),
            diff_details=json.dumps(diff),
            priority=6,
            xingji_id="xingji.update_collection",
            xingji_params=json.dumps(
                {"collection_id": existing.get("id"), "updates": diff}
            ),
            created_at=now_iso(),
        )

    def _create_delete_collection_delta(
        self, existing: Dict[str, Any]
    ) -> UniverseDelta:
        """创建"删除集合"差分"""
        return UniverseDelta(
            id=str(uuid.uuid4()),
            goal_id="",
            delta_type=DeltaType.delete_collection.value,
            target_type="collection",
            target_id=existing.get("id"),
            expected_state=json.dumps({}),
            actual_state=json.dumps(existing),
            diff_details=json.dumps({"action": "delete", "target": existing}),
            priority=4,
            xingji_id="xingji.delete_collection",
            xingji_params=json.dumps({"collection_id": existing.get("id")}),
            created_at=now_iso(),
        )

    def _create_add_document_delta(self, expected: Dict[str, Any]) -> UniverseDelta:
        """创建"添加文档"差分"""
        return UniverseDelta(
            id=str(uuid.uuid4()),
            goal_id="",
            delta_type=DeltaType.add_document.value,
            target_type="document",
            target_id=None,
            expected_state=json.dumps(expected),
            actual_state=json.dumps({}),
            diff_details=json.dumps({"action": "create", "data": expected}),
            priority=7,
            xingji_id="xingji.add_document",
            xingji_params=json.dumps(
                {
                    "collection_id": expected.get("collection_id"),
                    "content": expected.get("content"),
                    "content_type": expected.get("content_type", "text"),
                    "tags": expected.get("tags", []),
                }
            ),
            created_at=now_iso(),
        )

    def _create_create_relation_delta(
        self, expected: Dict[str, Any]
    ) -> UniverseDelta:
        """创建"创建关系"差分"""
        return UniverseDelta(
            id=str(uuid.uuid4()),
            goal_id="",
            delta_type=DeltaType.create_relation.value,
            target_type="relation",
            target_id=None,
            expected_state=json.dumps(expected),
            actual_state=json.dumps({}),
            diff_details=json.dumps({"action": "create", "data": expected}),
            priority=5,
            xingji_id="xingji.create_relation",
            xingji_params=json.dumps(
                {
                    "source_id": expected.get("source_id"),
                    "target_id": expected.get("target_id"),
                    "relation_type": expected.get("relation_type", "related_to"),
                    "description": expected.get("description"),
                }
            ),
            created_at=now_iso(),
        )

    # ===== 查找辅助方法 =====

    def _find_collection_by_name(
        self, name: Optional[str], collections: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """根据名称查找集合"""
        if not name:
            return None
        for col in collections:
            if col.get("name") == name:
                return col
        return None

    def _find_collection_by_id(
        self, col_id: Optional[str], collections: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """根据 ID 查找集合"""
        if not col_id:
            return None
        for col in collections:
            if col.get("id") == col_id:
                return col
        return None

    def _compute_dict_diff(
        self, actual: Dict[str, Any], expected: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算两个字典的差异"""
        diff = {}
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            if actual_value != expected_value:
                diff[key] = {"from": actual_value, "to": expected_value}
        return diff


class DeltaPrioritizer:
    """差分优先级调整器"""

    def adjust_priorities(
        self, deltas: List[UniverseDelta], context: Dict[str, Any]
    ) -> List[UniverseDelta]:
        return deltas
