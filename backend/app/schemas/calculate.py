from pydantic import BaseModel, Field


class CalculateRequest(BaseModel):
    labor_qty: float = Field(ge=0)
    labor_price: float = Field(ge=0)
    material_qty: float = Field(ge=0)
    material_price: float = Field(ge=0)
    machine_qty: float = Field(ge=0)
    machine_price: float = Field(ge=0)


class CalculateResponse(BaseModel):
    total: float
    currency: str
