from pydantic import BaseModel


class LineCalcResultOut(BaseModel):
    boq_item_id: int
    boq_code: str
    boq_name: str
    labor_cost: float
    material_cost: float
    machine_cost: float
    direct_cost: float
    management_fee: float
    profit: float
    regulatory_fee: float
    pre_tax_total: float
    tax: float
    total: float


class ProjectCalcSummary(BaseModel):
    total_direct: float
    total_management: float
    total_profit: float
    total_regulatory: float
    total_pre_tax: float
    total_tax: float
    total_measures: float = 0.0
    grand_total: float
    line_results: list[LineCalcResultOut]
