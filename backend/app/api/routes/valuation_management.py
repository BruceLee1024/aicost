import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.contract_measurement import ContractMeasurement
from app.models.payment_certificate import PaymentCertificate
from app.models.price_adjustment import PriceAdjustment
from app.models.project import Project
from app.models.project_valuation_config import ProjectValuationConfig
from app.schemas.valuation_management import (
    ContractMeasurementApprove,
    ContractMeasurementCreate,
    ContractMeasurementOut,
    PaymentCertificateCreate,
    PaymentCertificateOut,
    PriceAdjustmentCreate,
    PriceAdjustmentOut,
    ValuationOverviewOut,
    ValuationStageOut,
    ValuationStandardConfigOut,
    ValuationStandardConfigUpdate,
)
from app.services.audit_service import write_audit_log
from app.services.pricing_engine import _r2

router = APIRouter(tags=["valuation-management"])


_DEFAULT_STANDARD_CODE = "GB/T50500-2024"
_DEFAULT_STANDARD_NAME = "建设工程工程量清单计价标准"
_DEFAULT_EFFECTIVE_DATE = "2025-09-01"


def _must_get_project(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_or_create_config(project_id: int, db: Session) -> ProjectValuationConfig:
    row = (
        db.query(ProjectValuationConfig)
        .filter(ProjectValuationConfig.project_id == project_id)
        .first()
    )
    if row:
        return row
    row = ProjectValuationConfig(
        project_id=project_id,
        standard_code=_DEFAULT_STANDARD_CODE,
        standard_name=_DEFAULT_STANDARD_NAME,
        effective_date=_DEFAULT_EFFECTIVE_DATE,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _to_standard_out(row: ProjectValuationConfig) -> ValuationStandardConfigOut:
    return ValuationStandardConfigOut(
        project_id=row.project_id,
        standard_code=row.standard_code,
        standard_name=row.standard_name,
        effective_date=row.effective_date,
        locked=bool(row.locked_at),
        locked_at=row.locked_at,
    )


@router.get(
    "/projects/{project_id}/valuation-management/config",
    response_model=ValuationStandardConfigOut,
)
def get_valuation_config(project_id: int, db: Session = Depends(get_db)) -> ValuationStandardConfigOut:
    _must_get_project(project_id, db)
    config = _get_or_create_config(project_id, db)
    return _to_standard_out(config)


@router.put(
    "/projects/{project_id}/valuation-management/config",
    response_model=ValuationStandardConfigOut,
)
def update_valuation_config(
    project_id: int,
    payload: ValuationStandardConfigUpdate,
    db: Session = Depends(get_db),
) -> ValuationStandardConfigOut:
    _must_get_project(project_id, db)
    config = _get_or_create_config(project_id, db)

    if config.locked_at and config.standard_code != payload.standard_code:
        raise HTTPException(status_code=400, detail="当前项目计价标准已锁定，不能切换口径")

    config.standard_code = payload.standard_code
    config.standard_name = payload.standard_name
    config.effective_date = payload.effective_date
    if payload.lock_standard and not config.locked_at:
        config.locked_at = datetime.now(timezone.utc).isoformat()
    config.updated_at = datetime.now(timezone.utc).isoformat()

    db.commit()
    db.refresh(config)
    write_audit_log(
        db=db,
        project_id=project_id,
        action="update_valuation_standard",
        resource_type="valuation_config",
        resource_id=config.id,
        after_json=json.dumps(
            {
                "standard_code": config.standard_code,
                "standard_name": config.standard_name,
                "effective_date": config.effective_date,
                "locked_at": config.locked_at,
            },
            ensure_ascii=False,
        ),
    )
    return _to_standard_out(config)


@router.get(
    "/projects/{project_id}/valuation-management/overview",
    response_model=ValuationOverviewOut,
)
def get_valuation_overview(project_id: int, db: Session = Depends(get_db)) -> ValuationOverviewOut:
    _must_get_project(project_id, db)
    config = _get_or_create_config(project_id, db)

    boq_count = db.query(func.count(BoqItem.id)).filter(BoqItem.project_id == project_id).scalar() or 0
    measurement_count = (
        db.query(func.count(ContractMeasurement.id))
        .filter(ContractMeasurement.project_id == project_id)
        .scalar()
        or 0
    )
    adjustment_rows = db.query(PriceAdjustment).filter(PriceAdjustment.project_id == project_id).all()
    payment_rows = db.query(PaymentCertificate).filter(PaymentCertificate.project_id == project_id).all()
    adjustment_count = len(adjustment_rows)
    payment_count = len(payment_rows)
    adjustment_total = _r2(sum(r.amount for r in adjustment_rows))
    payment_net_total = _r2(sum(r.net_payable for r in payment_rows))

    stages = [
        ValuationStageOut(
            key="boq_compilation",
            label="清单编制",
            status="done" if boq_count > 0 else "pending",
            detail=f"清单项 {boq_count} 条",
        ),
        ValuationStageOut(
            key="limit_price",
            label="最高投标限价",
            status="done" if boq_count > 0 else "pending",
            detail="基于当前清单与规则口径",
        ),
        ValuationStageOut(
            key="bid_price",
            label="投标报价",
            status="in_progress" if boq_count > 0 else "pending",
            detail="报价与组价复核中",
        ),
        ValuationStageOut(
            key="contract_measurement",
            label="合同计量",
            status="done" if measurement_count > 0 else "pending",
            detail=f"计量记录 {measurement_count} 条",
        ),
        ValuationStageOut(
            key="price_adjustment",
            label="价款调整",
            status="done" if adjustment_count > 0 else "pending",
            detail=f"调整单 {adjustment_count} 条",
        ),
        ValuationStageOut(
            key="progress_payment",
            label="期中支付",
            status="done" if payment_count > 0 else "pending",
            detail=f"支付证书 {payment_count} 份",
        ),
        ValuationStageOut(
            key="final_settlement",
            label="竣工结算",
            status="in_progress" if payment_count > 0 else "pending",
            detail="可基于支付与调整生成结算对比",
        ),
    ]

    return ValuationOverviewOut(
        project_id=project_id,
        standard=_to_standard_out(config),
        stages=stages,
        boq_count=boq_count,
        measurement_count=measurement_count,
        adjustment_count=adjustment_count,
        payment_count=payment_count,
        adjustment_total=adjustment_total,
        payment_net_total=payment_net_total,
    )


@router.post(
    "/projects/{project_id}/valuation-management/measurements",
    response_model=ContractMeasurementOut,
)
def create_contract_measurement(
    project_id: int,
    payload: ContractMeasurementCreate,
    db: Session = Depends(get_db),
) -> ContractMeasurementOut:
    _must_get_project(project_id, db)
    boq = (
        db.query(BoqItem)
        .filter(BoqItem.id == payload.boq_item_id, BoqItem.project_id == project_id)
        .first()
    )
    if not boq:
        raise HTTPException(status_code=404, detail="BOQ item not found")

    prev_cumulative = (
        db.query(func.max(ContractMeasurement.cumulative_qty))
        .filter(
            ContractMeasurement.project_id == project_id,
            ContractMeasurement.boq_item_id == payload.boq_item_id,
        )
        .scalar()
        or 0.0
    )
    row = ContractMeasurement(
        project_id=project_id,
        boq_item_id=payload.boq_item_id,
        period_label=payload.period_label,
        measured_qty=payload.measured_qty,
        cumulative_qty=_r2(prev_cumulative + payload.measured_qty),
        note=payload.note,
        status="draft",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    write_audit_log(
        db=db,
        project_id=project_id,
        action="create_contract_measurement",
        resource_type="contract_measurement",
        resource_id=row.id,
        after_json=json.dumps(
            {
                "boq_item_id": row.boq_item_id,
                "period_label": row.period_label,
                "measured_qty": row.measured_qty,
                "cumulative_qty": row.cumulative_qty,
            },
            ensure_ascii=False,
        ),
    )
    return _measurement_out(row=row, boq=boq)


@router.get(
    "/projects/{project_id}/valuation-management/measurements",
    response_model=list[ContractMeasurementOut],
)
def list_contract_measurements(
    project_id: int,
    period_label: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ContractMeasurementOut]:
    _must_get_project(project_id, db)
    q = db.query(ContractMeasurement).filter(ContractMeasurement.project_id == project_id)
    if period_label:
        q = q.filter(ContractMeasurement.period_label == period_label)
    rows = q.order_by(ContractMeasurement.id.desc()).all()
    if not rows:
        return []
    boq_ids = {r.boq_item_id for r in rows}
    boq_map = {b.id: b for b in db.query(BoqItem).filter(BoqItem.id.in_(boq_ids)).all()}
    return [_measurement_out(row=r, boq=boq_map.get(r.boq_item_id)) for r in rows]


@router.post(
    "/projects/{project_id}/valuation-management/measurements/{measurement_id}:approve",
    response_model=ContractMeasurementOut,
)
def approve_contract_measurement(
    project_id: int,
    measurement_id: int,
    payload: ContractMeasurementApprove,
    db: Session = Depends(get_db),
) -> ContractMeasurementOut:
    _must_get_project(project_id, db)
    row = (
        db.query(ContractMeasurement)
        .filter(
            ContractMeasurement.project_id == project_id,
            ContractMeasurement.id == measurement_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Measurement not found")
    row.status = "approved"
    row.approved_by = payload.approved_by
    row.approved_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(row)
    boq = db.query(BoqItem).filter(BoqItem.id == row.boq_item_id).first()

    write_audit_log(
        db=db,
        project_id=project_id,
        action="approve_contract_measurement",
        resource_type="contract_measurement",
        resource_id=row.id,
        after_json=json.dumps(
            {
                "status": row.status,
                "approved_by": row.approved_by,
                "approved_at": row.approved_at,
            },
            ensure_ascii=False,
        ),
    )
    return _measurement_out(row=row, boq=boq)


@router.post(
    "/projects/{project_id}/valuation-management/adjustments",
    response_model=PriceAdjustmentOut,
)
def create_price_adjustment(
    project_id: int,
    payload: PriceAdjustmentCreate,
    db: Session = Depends(get_db),
) -> PriceAdjustmentOut:
    _must_get_project(project_id, db)
    boq = None
    if payload.boq_item_id is not None:
        boq = (
            db.query(BoqItem)
            .filter(BoqItem.id == payload.boq_item_id, BoqItem.project_id == project_id)
            .first()
        )
        if not boq:
            raise HTTPException(status_code=404, detail="BOQ item not found")

    row = PriceAdjustment(
        project_id=project_id,
        boq_item_id=payload.boq_item_id,
        adjustment_type=payload.adjustment_type,
        amount=payload.amount,
        reason=payload.reason,
        status=payload.status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    write_audit_log(
        db=db,
        project_id=project_id,
        action="create_price_adjustment",
        resource_type="price_adjustment",
        resource_id=row.id,
        after_json=json.dumps(
            {
                "adjustment_type": row.adjustment_type,
                "amount": row.amount,
                "status": row.status,
            },
            ensure_ascii=False,
        ),
    )
    return _adjustment_out(row=row, boq=boq)


@router.get(
    "/projects/{project_id}/valuation-management/adjustments",
    response_model=list[PriceAdjustmentOut],
)
def list_price_adjustments(project_id: int, db: Session = Depends(get_db)) -> list[PriceAdjustmentOut]:
    _must_get_project(project_id, db)
    rows = (
        db.query(PriceAdjustment)
        .filter(PriceAdjustment.project_id == project_id)
        .order_by(PriceAdjustment.id.desc())
        .all()
    )
    if not rows:
        return []
    boq_ids = {r.boq_item_id for r in rows if r.boq_item_id is not None}
    boq_map = {b.id: b for b in db.query(BoqItem).filter(BoqItem.id.in_(boq_ids)).all()} if boq_ids else {}
    return [_adjustment_out(row=r, boq=boq_map.get(r.boq_item_id)) for r in rows]


@router.post(
    "/projects/{project_id}/valuation-management/payments",
    response_model=PaymentCertificateOut,
)
def create_payment_certificate(
    project_id: int,
    payload: PaymentCertificateCreate,
    db: Session = Depends(get_db),
) -> PaymentCertificateOut:
    _must_get_project(project_id, db)
    net_payable = _r2(payload.gross_amount - payload.prepayment_deduction - payload.retention)
    row = PaymentCertificate(
        project_id=project_id,
        period_label=payload.period_label,
        gross_amount=payload.gross_amount,
        prepayment_deduction=payload.prepayment_deduction,
        retention=payload.retention,
        net_payable=net_payable,
        paid_amount=payload.paid_amount,
        status=payload.status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    write_audit_log(
        db=db,
        project_id=project_id,
        action="create_payment_certificate",
        resource_type="payment_certificate",
        resource_id=row.id,
        after_json=json.dumps(
            {
                "period_label": row.period_label,
                "net_payable": row.net_payable,
                "paid_amount": row.paid_amount,
                "status": row.status,
            },
            ensure_ascii=False,
        ),
    )
    return _payment_out(row)


@router.get(
    "/projects/{project_id}/valuation-management/payments",
    response_model=list[PaymentCertificateOut],
)
def list_payment_certificates(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[PaymentCertificateOut]:
    _must_get_project(project_id, db)
    rows = (
        db.query(PaymentCertificate)
        .filter(PaymentCertificate.project_id == project_id)
        .order_by(PaymentCertificate.id.desc())
        .all()
    )
    return [_payment_out(r) for r in rows]


def _measurement_out(row: ContractMeasurement, boq: BoqItem | None) -> ContractMeasurementOut:
    return ContractMeasurementOut(
        id=row.id,
        project_id=row.project_id,
        boq_item_id=row.boq_item_id,
        boq_code=boq.code if boq else "",
        boq_name=boq.name if boq else "",
        boq_unit=boq.unit if boq else "",
        period_label=row.period_label,
        measured_qty=row.measured_qty,
        cumulative_qty=row.cumulative_qty,
        status=row.status,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        note=row.note,
        created_at=row.created_at,
    )


def _adjustment_out(row: PriceAdjustment, boq: BoqItem | None) -> PriceAdjustmentOut:
    return PriceAdjustmentOut(
        id=row.id,
        project_id=row.project_id,
        boq_item_id=row.boq_item_id,
        boq_code=boq.code if boq else "",
        boq_name=boq.name if boq else "",
        adjustment_type=row.adjustment_type,
        amount=row.amount,
        status=row.status,
        reason=row.reason,
        created_at=row.created_at,
    )


def _payment_out(row: PaymentCertificate) -> PaymentCertificateOut:
    return PaymentCertificateOut(
        id=row.id,
        project_id=row.project_id,
        period_label=row.period_label,
        gross_amount=row.gross_amount,
        prepayment_deduction=row.prepayment_deduction,
        retention=row.retention,
        net_payable=row.net_payable,
        paid_amount=row.paid_amount,
        status=row.status,
        issued_at=row.issued_at,
    )

