from pydantic import BaseModel


class SnapshotCreate(BaseModel):
    label: str = ""


class SnapshotOut(BaseModel):
    id: int
    project_id: int
    label: str
    created_at: str
    grand_total: float


class DiffRequest(BaseModel):
    snapshot_a_id: int
    snapshot_b_id: int


class ChangeAttributionOut(BaseModel):
    quantity_change: bool = False
    quota_change: bool = False
    material_price_change: bool = False
    fee_rate_change: bool = False
    reasons: list[str] = []


class LineDiffOut(BaseModel):
    boq_code: str
    boq_name: str
    change_type: str
    old_total: float | None
    new_total: float | None
    delta: float
    attribution: ChangeAttributionOut | None = None


class DiffReportOut(BaseModel):
    snapshot_a_id: int
    snapshot_b_id: int
    old_grand_total: float
    new_grand_total: float
    grand_total_delta: float
    lines: list[LineDiffOut]
    explanation: str = ""
    price_changed: bool = False
    fee_rate_changed: bool = False
