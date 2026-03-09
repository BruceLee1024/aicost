"""Background task status API."""

import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.task_manager import TaskStatus, task_manager

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskStatusOut(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: float
    message: str
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: list[TaskStatusOut]


@router.get("/{task_id}", response_model=TaskStatusOut)
def get_task_status(task_id: str) -> TaskStatusOut:
    """Poll the status of a background task."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskStatusOut(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status.value,
        progress=task.progress,
        message=task.message,
        error=task.error,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@router.get("", response_model=TaskListResponse)
def list_tasks(task_type: Optional[str] = None) -> TaskListResponse:
    """List recent tasks, optionally filtered by type."""
    tasks = task_manager.list_tasks(task_type=task_type)
    return TaskListResponse(tasks=[
        TaskStatusOut(
            task_id=t.task_id,
            task_type=t.task_type,
            status=t.status.value,
            progress=t.progress,
            message=t.message,
            error=t.error,
            created_at=t.created_at,
            completed_at=t.completed_at,
        )
        for t in tasks[:20]
    ])


# ── Async batch valuate ──

class BatchValuateRequest(BaseModel):
    pass  # Could add filtering options later


class BatchValuateStarted(BaseModel):
    task_id: str
    message: str


@router.post("/projects/{project_id}/batch-valuate", response_model=BatchValuateStarted)
def start_batch_valuate(project_id: int) -> BatchValuateStarted:
    """Start async batch auto-valuate for all unbound items in a project."""
    task_id = task_manager.create_task("batch_valuate")

    def _run():
        db = SessionLocal()
        try:
            from app.models.boq_item import BoqItem
            from app.models.line_item_quota_binding import LineItemQuotaBinding
            from app.services.quota_match_service import match_quota_for_boq_item

            items = db.query(BoqItem).filter(BoqItem.project_id == project_id).all()
            # Find unbound items
            bound_ids = set()
            if items:
                bound_ids = {
                    row.boq_item_id
                    for row in db.query(LineItemQuotaBinding)
                    .filter(LineItemQuotaBinding.boq_item_id.in_([i.id for i in items]))
                    .all()
                }
            unbound = [i for i in items if i.id not in bound_ids]

            if not unbound:
                task_manager.complete_task(task_id, {"matched": 0, "total": len(items)})
                return

            matched = 0
            for idx, boq in enumerate(unbound):
                task_manager.update_progress(
                    task_id,
                    (idx + 1) / len(unbound),
                    f"处理 {idx + 1}/{len(unbound)}: {boq.name}",
                )
                candidates = match_quota_for_boq_item(boq_item_id=boq.id, project_id=project_id, db=db)
                if candidates:
                    best = candidates[0]
                    existing = (
                        db.query(LineItemQuotaBinding)
                        .filter(
                            LineItemQuotaBinding.boq_item_id == boq.id,
                            LineItemQuotaBinding.quota_item_id == best.quota_item_id,
                        )
                        .first()
                    )
                    if not existing:
                        db.add(LineItemQuotaBinding(
                            boq_item_id=boq.id,
                            quota_item_id=best.quota_item_id,
                            coefficient=1.0,
                        ))
                        boq.is_dirty = 1
                        matched += 1

            db.commit()
            task_manager.complete_task(task_id, {
                "matched": matched,
                "unbound_total": len(unbound),
                "project_items": len(items),
            })
        except Exception as exc:
            task_manager.fail_task(task_id, str(exc))
        finally:
            db.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return BatchValuateStarted(
        task_id=task_id,
        message=f"批量组价任务已启动 (task_id={task_id})",
    )
