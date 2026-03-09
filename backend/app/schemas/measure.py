from pydantic import BaseModel


class MeasureItemCreate(BaseModel):
    name: str
    calc_base: str = "direct"  # "direct" | "pre_tax"
    rate: float = 0
    amount: float = 0
    is_fixed: bool = False


class MeasureItemOut(BaseModel):
    id: int
    project_id: int
    name: str
    calc_base: str
    rate: float
    amount: float
    is_fixed: bool
