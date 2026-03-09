"""Background task manager with progress tracking.

Provides a simple in-memory task registry for long-running operations
(imports, batch valuation, etc.) so the frontend can poll for progress.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    task_id: str
    task_type: str  # "import_boq", "import_quota", "batch_valuate", etc.
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0
    message: str = ""
    result: Any = None
    error: str | None = None
    created_at: str = ""
    completed_at: str | None = None


class TaskManager:
    """Thread-safe in-memory task registry."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = threading.Lock()

    def create_task(self, task_type: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        task = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._tasks[task_id] = task
        return task_id

    def update_progress(self, task_id: str, progress: float, message: str = "") -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.RUNNING
                task.progress = min(progress, 1.0)
                task.message = message

    def complete_task(self, task_id: str, result: Any = None) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.COMPLETED
                task.progress = 1.0
                task.result = result
                task.completed_at = datetime.now(timezone.utc).isoformat()

    def fail_task(self, task_id: str, error: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.FAILED
                task.error = error
                task.completed_at = datetime.now(timezone.utc).isoformat()

    def get_task(self, task_id: str) -> TaskInfo | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, task_type: str | None = None) -> list[TaskInfo]:
        with self._lock:
            tasks = list(self._tasks.values())
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def cleanup_old(self, max_age_seconds: int = 3600) -> int:
        """Remove completed/failed tasks older than max_age_seconds."""
        now = datetime.now(timezone.utc)
        to_remove = []
        with self._lock:
            for tid, task in self._tasks.items():
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) and task.completed_at:
                    completed = datetime.fromisoformat(task.completed_at)
                    if (now - completed).total_seconds() > max_age_seconds:
                        to_remove.append(tid)
            for tid in to_remove:
                del self._tasks[tid]
        return len(to_remove)


# Global singleton
task_manager = TaskManager()
