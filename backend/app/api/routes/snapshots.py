from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.snapshot import Snapshot
from app.schemas.snapshot import (
    ChangeAttributionOut,
    DiffReportOut,
    DiffRequest,
    LineDiffOut,
    SnapshotCreate,
    SnapshotOut,
)
from app.services.snapshot_service import create_snapshot, diff_snapshots, generate_diff_explanation

router = APIRouter(tags=["snapshots"])


@router.post("/projects/{project_id}/snapshots", response_model=SnapshotOut)
def create_project_snapshot(
    project_id: int,
    payload: SnapshotCreate,
    db: Session = Depends(get_db),
) -> SnapshotOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    snap = create_snapshot(project_id=project_id, label=payload.label, db=db)
    return SnapshotOut(
        id=snap.id,
        project_id=snap.project_id,
        label=snap.label,
        created_at=snap.created_at,
        grand_total=snap.grand_total,
    )


@router.get("/projects/{project_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[SnapshotOut]:
    rows = (
        db.query(Snapshot)
        .filter(Snapshot.project_id == project_id)
        .order_by(Snapshot.id.desc())
        .all()
    )
    return [
        SnapshotOut(
            id=s.id,
            project_id=s.project_id,
            label=s.label,
            created_at=s.created_at,
            grand_total=s.grand_total,
        )
        for s in rows
    ]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
) -> SnapshotOut:
    snap = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return SnapshotOut(
        id=snap.id,
        project_id=snap.project_id,
        label=snap.label,
        created_at=snap.created_at,
        grand_total=snap.grand_total,
    )


@router.post("/projects/{project_id}/diff", response_model=DiffReportOut)
def diff_project_snapshots(
    project_id: int,
    payload: DiffRequest,
    db: Session = Depends(get_db),
) -> DiffReportOut:
    snap_a = db.query(Snapshot).filter(Snapshot.id == payload.snapshot_a_id).first()
    snap_b = db.query(Snapshot).filter(Snapshot.id == payload.snapshot_b_id).first()
    if not snap_a or not snap_b:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    if snap_a.project_id != project_id or snap_b.project_id != project_id:
        raise HTTPException(status_code=400, detail="Snapshots do not belong to this project")

    report = diff_snapshots(snap_a, snap_b)
    explanation = generate_diff_explanation(report)
    def _map_attribution(attr):
        if attr is None:
            return None
        return ChangeAttributionOut(
            quantity_change=attr.quantity_change,
            quota_change=attr.quota_change,
            material_price_change=attr.material_price_change,
            fee_rate_change=attr.fee_rate_change,
            reasons=attr.reasons,
        )

    return DiffReportOut(
        snapshot_a_id=report.snapshot_a_id,
        snapshot_b_id=report.snapshot_b_id,
        old_grand_total=report.old_grand_total,
        new_grand_total=report.new_grand_total,
        grand_total_delta=report.grand_total_delta,
        lines=[
            LineDiffOut(
                boq_code=ld.boq_code,
                boq_name=ld.boq_name,
                change_type=ld.change_type,
                old_total=ld.old_total,
                new_total=ld.new_total,
                delta=ld.delta,
                attribution=_map_attribution(ld.attribution),
            )
            for ld in report.lines
        ],
        explanation=explanation,
        price_changed=report.price_changed,
        fee_rate_changed=report.fee_rate_changed,
    )
