"""Audit log helper."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    *,
    project_id: int,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    actor: str = "system",
    before_json: str | None = None,
    after_json: str | None = None,
) -> AuditLog:
    log = AuditLog(
        project_id=project_id,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_json=before_json,
        after_json=after_json,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
