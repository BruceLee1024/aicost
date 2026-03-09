from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogOut

router = APIRouter(tags=["audit-logs"])


@router.get("/projects/{project_id}/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.project_id == project_id)
        .order_by(AuditLog.id.desc())
        .all()
    )
    return [
        AuditLogOut(
            id=r.id,
            project_id=r.project_id,
            actor=r.actor,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            before_json=r.before_json,
            after_json=r.after_json,
            timestamp=r.timestamp,
        )
        for r in rows
    ]
