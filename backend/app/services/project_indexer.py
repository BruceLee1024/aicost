"""Sprint 9 Phase 3 — index Project rows into the vector store.

Tiny, synchronous service. Run after a project is created/updated, or
called from a CLI / migration to bulk-index existing projects so the
``search_similar_projects`` tool has data to retrieve.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.ai.framework.vector_store import VectorStore
from app.models.boq_item import BoqItem
from app.models.project import Project

logger = logging.getLogger(__name__)


def build_project_text(p: Project, db: Session | None = None) -> str:
    """Compose the indexable text representation of a project.

    Combines: name, region, type, standard, description, top divisions
    (if a db session is provided so we can introspect BOQ).
    """
    parts: list[str] = [
        p.name or "",
        p.region or "",
        p.project_type or "",
        p.standard_type or "",
    ]
    if getattr(p, "description", None):
        parts.append(p.description)

    if db is not None:
        try:
            divisions = (
                db.query(BoqItem.division)
                .filter(BoqItem.project_id == p.id)
                .distinct()
                .all()
            )
            div_names = [d[0] for d in divisions if d and d[0]]
            if div_names:
                parts.append("分部: " + " / ".join(div_names))
        except Exception:  # pragma: no cover — defensive
            logger.debug("build_project_text: division enrich failed", exc_info=True)

    return "\n".join(s.strip() for s in parts if s and s.strip())


def project_meta(p: Project) -> dict[str, Any]:
    return {
        "name": p.name,
        "region": p.region,
        "project_type": p.project_type,
        "standard_type": p.standard_type,
        "currency": p.currency,
    }


def index_project(db: Session, project: Project) -> bool:
    """Embed and store a single project. Returns True on success."""
    store = VectorStore(db)
    text = build_project_text(project, db=db)
    if not text:
        return False
    try:
        store.upsert(
            namespace="project",
            ref_id=str(project.id),
            text=text,
            meta=project_meta(project),
            snippet=text[:500],
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        logger.exception("index_project failed for project_id=%s", project.id)
        return False


def reindex_all_projects(db: Session) -> int:
    """Re-index every project. Returns indexed count."""
    store = VectorStore(db)
    projects = db.query(Project).all()
    items = []
    for p in projects:
        text = build_project_text(p, db=db)
        if not text:
            continue
        items.append(
            {
                "ref_id": str(p.id),
                "text": text,
                "meta": project_meta(p),
                "snippet": text[:500],
            }
        )
    if not items:
        return 0
    n = store.upsert_many("project", items)
    db.commit()
    return n
