from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.snapshot import Snapshot
from app.services.export_service import export_diff_report, export_valuation_report

import io

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/valuation-report")
def download_valuation_report(
    project_id: int,
    db: Session = Depends(get_db),
):
    """Generate and download a valuation report Excel file."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    file_bytes = export_valuation_report(project_id=project_id, db=db)
    filename = f"valuation_report_{project.name}_{project_id}.xlsx"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/diff-report")
def download_diff_report(
    snapshot_a_id: int,
    snapshot_b_id: int,
    db: Session = Depends(get_db),
):
    """Generate and download a diff report Excel file."""
    snap_a = db.query(Snapshot).filter(Snapshot.id == snapshot_a_id).first()
    snap_b = db.query(Snapshot).filter(Snapshot.id == snapshot_b_id).first()
    if not snap_a or not snap_b:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    file_bytes = export_diff_report(snap_a, snap_b)
    filename = f"diff_report_{snapshot_a_id}_vs_{snapshot_b_id}.xlsx"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
