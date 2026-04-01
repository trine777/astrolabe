"""
星图 XingTu - 事件流（影澜轩）

事件驱动架构，用 LanceDB 表存储事件，支持事件发射、历史查询和订阅。
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from .models import Event, now_iso

if TYPE_CHECKING:
    from .store import XingkongzuoStore

logger = logging.getLogger(__name__)


class YinglanxuanEvents:
    """
    影澜轩 - 事件流与审计

    记录星图中所有变更事件，提供审计追踪能力。
    支持事件订阅回调机制。
    """

    def __init__(self, store: XingkongzuoStore):
        self.store = store
        self._subscribers: Dict[str, List[Callable]] = {}

    def emit(
        self,
        event_type: str,
        target_type: str,
        target_id: Optional[str] = None,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
        description: Optional[str] = None,
        before_snapshot: Optional[str] = None,
        after_snapshot: Optional[str] = None,
    ) -> dict:
        """
        发射事件

        Args:
            event_type: 事件类型 (created, updated, deleted, searched, inferred, etc.)
            target_type: 目标类型 (collection, document, relation, memory)
            target_id: 目标 ID
            actor_type: 操作者类型 (user, ai, system)
            actor_id: 操作者 ID
            description: 事件描述
            before_snapshot: 变更前快照 JSON
            after_snapshot: 变更后快照 JSON

        Returns:
            事件字典
        """
        event = Event(
            id=str(uuid.uuid4()),
            timestamp=now_iso(),
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            actor_type=actor_type,
            actor_id=actor_id,
            description=description,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        event_dict = event.model_dump()

        try:
            self.store.add_event(event_dict)
            logger.debug(f"事件已记录: {event_type} on {target_type}/{target_id}")
        except Exception as e:
            logger.error(f"事件记录失败: {e}")

        # 通知订阅者
        self._notify_subscribers(event_type, event_dict)

        return event_dict

    def get_history(
        self,
        target_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """
        查询事件历史

        Args:
            target_id: 按目标 ID 过滤
            event_type: 按事件类型过滤
            since: 起始时间 (ISO format)
            limit: 返回数量限制

        Returns:
            事件列表
        """
        events = self.store.get_events(
            target_id=target_id,
            event_type=event_type,
            limit=limit,
        )

        # 如果指定了 since，进行时间过滤
        if since:
            events = [e for e in events if e.get("timestamp", "") >= since]

        # 清理内部字段
        cleaned = []
        for e in events:
            cleaned.append({k: v for k, v in e.items() if not k.startswith("_")})

        return cleaned

    def subscribe(
        self,
        event_types: Optional[List[str]] = None,
        callback: Optional[Callable] = None,
    ) -> str:
        """
        订阅事件

        Args:
            event_types: 要订阅的事件类型列表，None 表示订阅所有
            callback: 回调函数，接收事件字典

        Returns:
            订阅 ID
        """
        if callback is None:
            return ""

        sub_id = str(uuid.uuid4())
        types = event_types or ["*"]

        for event_type in types:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

        logger.debug(f"事件订阅已注册: {sub_id} -> {types}")
        return sub_id

    def _notify_subscribers(self, event_type: str, event_dict: dict) -> None:
        """通知订阅者"""
        # 通知特定类型的订阅者
        callbacks = self._subscribers.get(event_type, [])
        # 通知通配符订阅者
        callbacks = callbacks + self._subscribers.get("*", [])

        for callback in callbacks:
            try:
                callback(event_dict)
            except Exception as e:
                logger.error(f"事件回调执行失败: {e}")
