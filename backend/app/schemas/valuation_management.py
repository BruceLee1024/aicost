from pydantic import BaseModel, Field


class ValuationStandardConfigOut(BaseModel):
    project_id: int
    standard_code: str
    standard_name: str
    effective_date: str
    locked: bool
    locked_at: str | None


class ValuationStandardConfigUpdate(BaseModel):
    standard_code: str = "GB/T50500-2024"
    standard_name: str = "建设工程工程量清单计价标准"
    effective_date: str = "2025-09-01"
    lock_standard: bool = True


class ValuationStageOut(BaseModel):
    key: str
    label: str
    status: str
    detail: str = ""


class ValuationOverviewOut(BaseModel):
    project_id: int
    standard: ValuationStandardConfigOut
    stages: list[ValuationStageOut]
    boq_count: int
    measurement_count: int
    adjustment_count: int
    payment_count: int
    adjustment_total: float
    payment_net_total: float


class ContractMeasurementCreate(BaseModel):
    boq_item_id: int
    period_label: str
    measured_qty: float = Field(ge=0)
    note: str = ""


class ContractMeasurementApprove(BaseModel):
    approved_by: str = "system"


class ContractMeasurementOut(BaseModel):
    id: int
    project_id: int
    boq_item_id: int
    boq_code: str
    boq_name: str
    boq_unit: str
    period_label: str
    measured_qty: float
    cumulative_qty: float
    status: str
    approved_by: str
    approved_at: str
    note: str
    created_at: str


class PriceAdjustmentCreate(BaseModel):
    adjustment_type: str = "change_order"
    boq_item_id: int | None = None
    amount: float
    reason: str = ""
    status: str = "draft"


class PriceAdjustmentOut(BaseModel):
    id: int
    project_id: int
    boq_item_id: int | None
    boq_code: str = ""
    boq_name: str = ""
    adjustment_type: str
    amount: float
    status: str
    reason: str
    created_at: str


class PaymentCertificateCreate(BaseModel):
    period_label: str
    gross_amount: float = 0
    prepayment_deduction: float = 0
    retention: float = 0
    paid_amount: float = 0
    status: str = "issued"


class PaymentCertificateOut(BaseModel):
    id: int
    project_id: int
    period_label: str
    gross_amount: float
    prepayment_deduction: float
    retention: float
    net_payable: float
    paid_amount: float
    status: str
    issued_at: str

