from pydantic import BaseModel


class QuotaRef(BaseModel):
    quota_code: str
    quota_name: str
    unit: str
    labor_qty: float
    material_qty: float
    machine_qty: float


class BindingRef(BaseModel):
    binding_id: int
    coefficient: float
    direct_cost: float | None = None
    quota: QuotaRef


class PriceSnapshot(BaseModel):
    labor_price: float
    material_price: float
    machine_price: float


class CalcBreakdown(BaseModel):
    direct_cost: float
    management_fee: float
    profit: float
    regulatory_fee: float
    pre_tax_total: float
    tax: float
    total: float


class CalcProvenance(BaseModel):
    boq_item_id: int
    boq_code: str
    boq_name: str
    boq_unit: str
    boq_quantity: float
    bindings: list[BindingRef]
    price_snapshot: PriceSnapshot
    calc_breakdown: CalcBreakdown | None
    unit_price: float | None
    calc_total: float | None
    fee_config_snapshot: dict
    explanation: str
