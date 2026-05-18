"""Sprint 9 — Phase 2: BOQ draft preview & commit endpoints.

These endpoints work hand-in-hand with the ``propose_boq_items`` tool:

  1. The Setup-Agent calls ``propose_boq_items`` which stashes the draft
     in the process-level draft store keyed by ``draft_token``.
  2. The frontend listens for ``tool_result`` SSE events, sees an
     ``action: "drafted"`` payload with a ``draft_token``, then calls
     ``GET /api/projects/{pid}/boq-drafts/{token}`` to load the rows
     into <BoqDraftEditor>.
  3. After the user edits and clicks "提交"，the frontend calls
     ``POST /api/projects/{pid}/boq-drafts/{token}/commit`` with the
     final items array. The backend writes them via the same logic
     used by ``batch_create_boq_items``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.framework.context import AgentContext
from app.ai.framework.draft_store import get_draft_store
from app.ai.framework.tool_registry import registry
import app.ai.tools.project_tools  # noqa: F401 — ensure tool registered
from app.db.session import get_db
from app.models.project import Project

logger = logging.getLogger(__name__)
router = APIRouter(tags=["boq-drafts"])


# ─── Schemas ────────────────────────────────────────────────────


class BoqDraftItem(BaseModel):
    draft_id: str | None = None
    code: str
    name: str
    unit: str
    quantity: float
    division: str = ""
    characteristics: str = ""
    remark: str = ""


class BoqDraftResponse(BaseModel):
    token: str
    project_id: int
    created_at: float
    items: list[BoqDraftItem]


class CommitRequest(BaseModel):
    items: list[BoqDraftItem] = Field(..., description="用户编辑后的最终清单项")


class CommitResponse(BaseModel):
    created_count: int
    created_ids: list[int]
    division_summary: dict[str, int]
    errors: list[str]


# ─── Routes ────────────────────────────────────────────────────


@router.get(
    "/projects/{project_id}/boq-drafts",
    summary="列出某项目的所有未提交草稿",
)
def list_drafts(project_id: int) -> list[BoqDraftResponse]:
    store = get_draft_store()
    out: list[BoqDraftResponse] = []
    for tok, entry in store.list_for_project(project_id):
        out.append(
            BoqDraftResponse(
                token=tok,
                project_id=entry.project_id,
                created_at=entry.created_at,
                items=[BoqDraftItem(**i) for i in entry.items],
            )
        )
    out.sort(key=lambda d: d.created_at, reverse=True)
    return out


@router.get(
    "/projects/{project_id}/boq-drafts/{token}",
    response_model=BoqDraftResponse,
    summary="读取指定草稿，用于前端可编辑表格",
)
def get_draft(project_id: int, token: str) -> BoqDraftResponse:
    entry = get_draft_store().get(token)
    if entry is None:
        raise HTTPException(status_code=404, detail="草稿不存在或已过期")
    if entry.project_id and entry.project_id != project_id:
        raise HTTPException(status_code=404, detail="草稿不属于该项目")
    return BoqDraftResponse(
        token=token,
        project_id=entry.project_id,
        created_at=entry.created_at,
        items=[BoqDraftItem(**i) for i in entry.items],
    )


@router.post(
    "/projects/{project_id}/boq-drafts/{token}/commit",
    response_model=CommitResponse,
    summary="将编辑后的草稿写入数据库",
)
def commit_draft(
    project_id: int,
    token: str,
    payload: CommitRequest,
    db: Session = Depends(get_db),
) -> CommitResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not payload.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    # Reuse batch_create_boq_items via the registry so all dedup/sort
    # logic stays in one place.
    ctx = AgentContext(db=db, project_id=project_id)
    items_json = "[" + ",".join(
        _item_to_json(item) for item in payload.items
    ) + "]"

    raw = registry.execute("batch_create_boq_items", {"items": items_json}, ctx)
    import json

    parsed: dict[str, Any] = json.loads(raw)
    if "error" in parsed:
        raise HTTPException(status_code=400, detail=parsed["error"])

    # Drop the draft after a successful commit
    get_draft_store().pop(token)

    return CommitResponse(
        created_count=parsed.get("created_count", 0),
        created_ids=parsed.get("created_ids", []),
        division_summary=parsed.get("division_summary", {}),
        errors=parsed.get("errors", []),
    )


@router.delete(
    "/projects/{project_id}/boq-drafts/{token}",
    summary="放弃草稿",
)
def discard_draft(project_id: int, token: str) -> dict[str, Any]:
    entry = get_draft_store().pop(token)
    if entry is None:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return {"discarded": True, "token": token}


# ─── Helpers ────────────────────────────────────────────────────


def _item_to_json(item: BoqDraftItem) -> str:
    import json

    return json.dumps(item.model_dump(), ensure_ascii=False)
