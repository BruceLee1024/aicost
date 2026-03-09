from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.boq_item import BoqItem
from app.models.comment import Comment
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.project import Project
from app.schemas.project import DashboardSummaryOut, ProjectCreate, ProjectOut
from app.services.validation_service import Severity, validate_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = Project(
        name=payload.name,
        region=payload.region,
        standard_type=payload.standard_type,
        language=payload.language,
        currency=payload.currency,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_out(project)


def _project_out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id, name=p.name, region=p.region,
        standard_type=p.standard_type, language=p.language, currency=p.currency,
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    rows = db.query(Project).all()
    return [_project_out(r) for r in rows]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_out(project)


@router.get("/{project_id}/dashboard-summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(project_id: int, db: Session = Depends(get_db)) -> DashboardSummaryOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    boq_rows = db.query(BoqItem.id, BoqItem.is_dirty).filter(BoqItem.project_id == project_id).all()
    boq_ids = [r.id for r in boq_rows]
    boq_count = len(boq_rows)
    dirty_count = sum(1 for r in boq_rows if r.is_dirty)

    bound_count = 0
    if boq_ids:
        bound_count = (
            db.query(func.count(func.distinct(LineItemQuotaBinding.boq_item_id)))
            .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
            .scalar()
            or 0
        )
    unbound_count = max(boq_count - bound_count, 0)

    issues = validate_project(project_id=project_id, db=db)
    validation_total = len(issues)
    validation_errors = sum(1 for i in issues if i.severity == Severity.ERROR)
    validation_warnings = sum(1 for i in issues if i.severity == Severity.WARNING)

    recent_audit_count = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.project_id == project_id)
        .scalar()
        or 0
    )
    recent_comment_count = (
        db.query(func.count(Comment.id))
        .filter(Comment.project_id == project_id)
        .scalar()
        or 0
    )

    return DashboardSummaryOut(
        project_id=project_id,
        boq_count=boq_count,
        unbound_count=unbound_count,
        dirty_count=dirty_count,
        validation_total=validation_total,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
        recent_audit_count=recent_audit_count,
        recent_comment_count=recent_comment_count,
    )
