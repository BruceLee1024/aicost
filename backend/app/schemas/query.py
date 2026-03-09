from pydantic import BaseModel


class QueryRequest(BaseModel):
    q: str


class QueryHit(BaseModel):
    boq_item_id: int
    code: str
    name: str
    unit: str
    quantity: float
    reason: str


class QueryResponse(BaseModel):
    query: str
    total_hits: int
    hits: list[QueryHit]
