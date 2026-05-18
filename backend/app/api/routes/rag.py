"""Sprint 9 Phase 3 — RAG-related HTTP endpoints.

Three groups:

  * Similar projects: GET / POST under /projects/{id}
  * Skill chunk ingestion: POST /skills/{name}/chunks
  * Reindex helpers (admin)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.framework.vector_store import VectorStore
from app.db.session import get_db
from app.models.project import Project
from app.services.project_indexer import (
    build_project_text,
    index_project,
    project_meta,
    reindex_all_projects,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rag"])


# ─── Schemas ────────────────────────────────────────────────────


class SimilarProject(BaseModel):
    project_id: int
    name: str
    region: str
    project_type: str
    standard_type: str
    score: float
    summary: str


class SimilarProjectsResponse(BaseModel):
    project_id: int
    matched_count: int
    results: list[SimilarProject]


class SkillChunkUpload(BaseModel):
    skill_name: str = Field(..., description="技能/规范名称，例如 GB50500")
    text: str = Field(..., description="完整的规范文本（将被切块后入库）")
    section: str | None = None
    chunk_size: int = Field(800, ge=100, le=4000, description="每块字符数")
    overlap: int = Field(80, ge=0, le=500, description="相邻块重叠字符数")


class SkillChunkResponse(BaseModel):
    skill_name: str
    chunks_indexed: int


# ─── Routes: similar projects ──────────────────────────────────


@router.get(
    "/projects/{project_id}/similar",
    response_model=SimilarProjectsResponse,
    summary="返回与该项目最相似的历史项目",
)
def similar_projects(
    project_id: int,
    top_n: int = 5,
    min_score: float = 0.0,
    db: Session = Depends(get_db),
) -> SimilarProjectsResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(404, "项目不存在")

    text = build_project_text(project, db=db)
    if not text:
        return SimilarProjectsResponse(
            project_id=project_id, matched_count=0, results=[]
        )

    store = VectorStore(db)
    hits = store.search(
        "project",
        text,
        top_n=max(1, min(top_n, 20)),
        min_score=min_score or None,
        exclude_ref_ids={str(project_id)},
    )

    results: list[SimilarProject] = []
    for h in hits:
        try:
            pid = int(h.ref_id)
        except ValueError:
            continue
        meta = h.meta or {}
        results.append(
            SimilarProject(
                project_id=pid,
                name=meta.get("name", ""),
                region=meta.get("region", ""),
                project_type=meta.get("project_type", ""),
                standard_type=meta.get("standard_type", ""),
                score=round(h.score, 4),
                summary=(h.snippet or "")[:300],
            )
        )

    return SimilarProjectsResponse(
        project_id=project_id,
        matched_count=len(results),
        results=results,
    )


@router.post(
    "/projects/{project_id}/index",
    summary="（重新）索引该项目到向量库",
)
def index_one_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(404, "项目不存在")
    ok = index_project(db, project)
    return {
        "project_id": project_id,
        "indexed": ok,
        "meta": project_meta(project),
    }


@router.post(
    "/projects/index/all",
    summary="一键重建所有项目的向量索引（管理员）",
)
def index_all_projects(db: Session = Depends(get_db)) -> dict[str, Any]:
    n = reindex_all_projects(db)
    return {"indexed_count": n}


# ─── Routes: skill chunks ──────────────────────────────────────


def _chunk_text(text: str, size: int, overlap: int) -> list[tuple[int, str]]:
    """Sliding-window chunker. Returns list of (chunk_index, snippet).

    Falls back to fixed-size character chunking with `overlap` trailing
    characters carried into the next chunk for context continuity.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    size = max(100, size)
    overlap = max(0, min(overlap, size - 50))
    out: list[tuple[int, str]] = []
    i = 0
    idx = 0
    while i < len(text):
        chunk = text[i : i + size]
        if not chunk:
            break
        out.append((idx, chunk))
        idx += 1
        if i + size >= len(text):
            break
        i += size - overlap
    return out


@router.post(
    "/skills/chunks/upload",
    response_model=SkillChunkResponse,
    summary="上传技能/规范文本，切块后写入向量库",
)
def upload_skill_chunks(
    payload: SkillChunkUpload = Body(...),
    db: Session = Depends(get_db),
) -> SkillChunkResponse:
    chunks = _chunk_text(payload.text, payload.chunk_size, payload.overlap)
    if not chunks:
        raise HTTPException(400, "文本为空或切块结果为零")

    store = VectorStore(db)
    items = [
        {
            "ref_id": payload.skill_name,
            "sub_key": f"c{idx:04d}",
            "text": snippet,
            "snippet": snippet,
            "meta": {
                "skill_name": payload.skill_name,
                "section": payload.section or "",
                "chunk_index": idx,
            },
        }
        for idx, snippet in chunks
    ]
    n = store.upsert_many("skill_chunk", items)
    db.commit()
    return SkillChunkResponse(skill_name=payload.skill_name, chunks_indexed=n)
