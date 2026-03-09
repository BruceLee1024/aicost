from pydantic import BaseModel


class MaterialPriceCreate(BaseModel):
    code: str
    name: str
    spec: str = ""
    unit: str
    unit_price: float
    source: str = "manual"
    region: str = ""
    effective_date: str = "1970-01-01"


class MaterialPriceOut(BaseModel):
    id: int
    code: str
    name: str
    spec: str
    unit: str
    unit_price: float
    source: str
    region: str
    effective_date: str


class BatchMaterialPriceRequest(BaseModel):
    items: list[MaterialPriceCreate]
