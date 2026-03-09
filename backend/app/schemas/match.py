from pydantic import BaseModel


class MatchCandidateOut(BaseModel):
    quota_item_id: int
    quota_code: str
    quota_name: str
    unit: str
    confidence: float
    reasons: list[str]
