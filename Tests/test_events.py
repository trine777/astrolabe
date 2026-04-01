"""
星图 XingTu - 事件流测试

测试 YinglanxuanEvents 的事件发射、历史查询和订阅功能。
"""

from __future__ import annotations

import uuid

import pytest

from xingtu.store import XingkongzuoStore
from xingtu.events import YinglanxuanEvents
from xingtu.models import now_iso


@pytest.fixture
def store(tmp_path):
    """创建临时存储实例"""
    s = XingkongzuoStore(str(tmp_path / "test_db"))
    s.initialize()
    return s


@pytest.fixture
def events(store):
    """创建事件流实例"""
    return YinglanxuanEvents(store)


class TestEventEmit:
    """事件发射测试"""

    def test_emit_event(self, events):
        result = events.emit(
            event_type="created",
            target_type="collection",
            target_id="test-col-1",
            description="创建了测试集合",
        )
        assert result["event_type"] == "created"
        assert result["target_type"] == "collection"
        assert result["target_id"] == "test-col-1"
        assert result["id"]  # 应有 UUID

    def test_emit_event_with_actor(self, events):
        result = events.emit(
            event_type="updated",
            target_type="document",
            target_id="doc-1",
            actor_type="ai",
            actor_id="claude",
            description="AI 更新了文档",
        )
        assert result["actor_type"] == "ai"
        assert result["actor_id"] == "claude"

    def test_emit_event_with_snapshots(self, events):
        result = events.emit(
            event_type="updated",
            target_type="collection",
            target_id="col-1",
            before_snapshot='{"status": "draft"}',
            after_snapshot='{"status": "confirmed"}',
        )
        assert result["before_snapshot"] == '{"status": "draft"}'
        assert result["after_snapshot"] == '{"status": "confirmed"}'


class TestEventHistory:
    """事件历史查询测试"""

    def test_get_history(self, events):
        # 发射几个事件
        events.emit(event_type="created", target_type="collection", target_id="col-1")
        events.emit(event_type="updated", target_type="collection", target_id="col-1")
        events.emit(event_type="deleted", target_type="document", target_id="doc-1")

        history = events.get_history()
        assert len(history) >= 3

    def test_get_history_by_target(self, events):
        events.emit(event_type="created", target_type="collection", target_id="target-A")
        events.emit(event_type="created", target_type="collection", target_id="target-B")

        history = events.get_history(target_id="target-A")
        assert len(history) >= 1
        for e in history:
            assert e["target_id"] == "target-A"

    def test_get_history_by_type(self, events):
        events.emit(event_type="created", target_type="collection")
        events.emit(event_type="searched", target_type="document")

        history = events.get_history(event_type="searched")
        assert len(history) >= 1
        for e in history:
            assert e["event_type"] == "searched"

    def test_get_history_cleaned(self, events):
        events.emit(event_type="created", target_type="collection")
        history = events.get_history()
        for e in history:
            # 不应包含内部字段
            for key in e:
                assert not key.startswith("_")


class TestEventSubscription:
    """事件订阅测试"""

    def test_subscribe_and_notify(self, events):
        received = []

        def callback(event_dict):
            received.append(event_dict)

        events.subscribe(event_types=["created"], callback=callback)
        events.emit(event_type="created", target_type="collection")

        assert len(received) == 1
        assert received[0]["event_type"] == "created"

    def test_subscribe_wildcard(self, events):
        received = []

        def callback(event_dict):
            received.append(event_dict)

        events.subscribe(event_types=None, callback=callback)  # 订阅所有
        events.emit(event_type="created", target_type="collection")
        events.emit(event_type="updated", target_type="document")

        assert len(received) == 2

    def test_subscribe_no_callback(self, events):
        sub_id = events.subscribe(event_types=["created"], callback=None)
        assert sub_id == ""

    def test_callback_error_handled(self, events):
        def bad_callback(event_dict):
            raise ValueError("回调错误")

        events.subscribe(event_types=["created"], callback=bad_callback)
        # 不应抛出异常
        result = events.emit(event_type="created", target_type="collection")
        assert result["event_type"] == "created"
