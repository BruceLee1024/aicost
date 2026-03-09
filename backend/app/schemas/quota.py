from pydantic import BaseModel


class QuotaItemOut(BaseModel):
    id: int
    quota_code: str
    name: str
    unit: str
    labor_qty: float
    material_qty: float
    machine_qty: float


class QuotaImportResult(BaseModel):
    imported: int
    skipped: int
    items: list[QuotaItemOut]


# --- Binding schemas ---

class BindingRequest(BaseModel):
    quota_item_id: int
    coefficient: float = 1.0

class BindingPair(BaseModel):
    boq_item_id: int
    quota_item_id: int
    coefficient: float = 1.0


class BatchBindingRequest(BaseModel):
    bindings: list[BindingPair]


class BatchReplaceBindingRequest(BaseModel):
    bindings: list[BindingPair]


class BindingOut(BaseModel):
    id: int
    boq_item_id: int
    quota_item_id: int
    coefficient: float


class BindingClearOut(BaseModel):
    boq_item_id: int
    removed: int


class BindingWithQuota(BaseModel):
    binding_id: int
    boq_item_id: int
    quota_item_id: int
    coefficient: float
    quota_code: str
    quota_name: str
    quota_unit: str
    labor_qty: float
    material_qty: float
    machine_qty: float
