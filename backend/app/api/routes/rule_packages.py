from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.rule_package import RulePackage
from app.schemas.project import ProjectOut
from app.schemas.rule_package import RulePackageBindRequest, RulePackageCreate, RulePackageOut
from app.services.audit_service import write_audit_log

router = APIRouter(tags=["rule-packages"])


@router.post("/rule-packages", response_model=RulePackageOut)
def create_rule_package(
    payload: RulePackageCreate,
    db: Session = Depends(get_db),
) -> RulePackageOut:
    rp = RulePackage(**payload.model_dump())
    db.add(rp)
    db.commit()
    db.refresh(rp)
    return _to_out(rp)


@router.get("/rule-packages", response_model=list[RulePackageOut])
def list_rule_packages(db: Session = Depends(get_db)) -> list[RulePackageOut]:
    rows = db.query(RulePackage).all()
    return [_to_out(r) for r in rows]


@router.post("/projects/{project_id}/rule-package:bind", response_model=ProjectOut)
def bind_rule_package(
    project_id: int,
    payload: RulePackageBindRequest,
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    rp = db.query(RulePackage).filter(RulePackage.id == payload.rule_package_id).first()
    if not rp:
        raise HTTPException(status_code=404, detail="Rule package not found")

    old_rp_id = project.rule_package_id
    project.rule_package_id = rp.id
    db.commit()
    db.refresh(project)

    write_audit_log(
        db=db,
        project_id=project.id,
        action="bind_rule_package",
        resource_type="project",
        resource_id=project.id,
        before_json=f'{{"rule_package_id": {old_rp_id}}}',
        after_json=f'{{"rule_package_id": {rp.id}}}',
    )

    return ProjectOut(id=project.id, name=project.name, region=project.region)


def _to_out(rp: RulePackage) -> RulePackageOut:
    return RulePackageOut(
        id=rp.id,
        name=rp.name,
        region=rp.region,
        management_rate=rp.management_rate,
        profit_rate=rp.profit_rate,
        regulatory_rate=rp.regulatory_rate,
        tax_rate=rp.tax_rate,
        rounding_rule=rp.rounding_rule,
        version=rp.version,
    )
