"""
星图 XingTu - 任务调度（序律腺）

简单的任务调度器，支持定时任务和一次性任务。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from .models import now_iso

logger = logging.getLogger(__name__)


class ScheduledTask:
    """调度任务"""

    def __init__(
        self,
        task_id: str,
        name: str,
        callback: Callable,
        interval_seconds: Optional[float] = None,
        run_once: bool = False,
    ):
        self.task_id = task_id
        self.name = name
        self.callback = callback
        self.interval_seconds = interval_seconds
        self.run_once = run_once
        self.last_run: Optional[str] = None
        self.run_count: int = 0
        self.is_active: bool = True
        self.created_at: str = now_iso()


class XuluxianScheduler:
    """
    序律腺 - 任务调度器

    管理定时任务和一次性任务：
    - 记忆衰减（定期降低 Agent 记忆重要性）
    - 数据库优化（定期压缩和清理）
    - 自定义任务
    """

    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def schedule(
        self,
        name: str,
        callback: Callable,
        interval_seconds: float = 3600,
        run_once: bool = False,
    ) -> str:
        """
        注册调度任务

        Args:
            name: 任务名称
            callback: 回调函数
            interval_seconds: 执行间隔（秒）
            run_once: 是否只执行一次

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            callback=callback,
            interval_seconds=interval_seconds,
            run_once=run_once,
        )

        with self._lock:
            self._tasks[task_id] = task

        logger.info(f"任务已注册: {name} (间隔: {interval_seconds}s, 一次性: {run_once})")
        return task_id

    def cancel(self, task_id: str) -> bool:
        """取消调度任务"""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].is_active = False
                del self._tasks[task_id]
                logger.info(f"任务已取消: {task_id}")
                return True
        return False

    def start(self) -> None:
        """启动调度器（后台线程）"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("序律腺调度器已启动")

    def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("序律腺调度器已停止")

    def run_now(self, task_id: str) -> bool:
        """立即执行指定任务"""
        with self._lock:
            task = self._tasks.get(task_id)

        if not task or not task.is_active:
            return False

        self._execute_task(task)
        return True

    def list_tasks(self) -> List[dict]:
        """列出所有调度任务"""
        with self._lock:
            return [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "interval_seconds": t.interval_seconds,
                    "run_once": t.run_once,
                    "last_run": t.last_run,
                    "run_count": t.run_count,
                    "is_active": t.is_active,
                    "created_at": t.created_at,
                }
                for t in self._tasks.values()
            ]

    def _run_loop(self) -> None:
        """调度循环"""
        while self._running:
            now = time.time()

            with self._lock:
                tasks_to_run = []
                for task in self._tasks.values():
                    if not task.is_active:
                        continue

                    if task.last_run is None:
                        # 首次运行
                        tasks_to_run.append(task)
                    elif task.interval_seconds:
                        last_run_time = datetime.fromisoformat(task.last_run)
                        elapsed = (
                            datetime.now(timezone.utc) - last_run_time
                        ).total_seconds()
                        if elapsed >= task.interval_seconds:
                            tasks_to_run.append(task)

            for task in tasks_to_run:
                self._execute_task(task)
                if task.run_once:
                    self.cancel(task.task_id)

            time.sleep(1)  # 每秒检查一次

    def _execute_task(self, task: ScheduledTask) -> None:
        """执行任务"""
        try:
            logger.debug(f"执行任务: {task.name}")
            task.callback()
            task.last_run = now_iso()
            task.run_count += 1
        except Exception as e:
            logger.error(f"任务执行失败 [{task.name}]: {e}")

    @property
    def is_running(self) -> bool:
        """调度器是否在运行"""
        return self._running
