from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    region: str
    standard_type: str = "GB50500"  # GB50500 | HKSMM4
    language: str = "zh"  # zh | en | bilingual
    currency: str = "CNY"  # CNY | HKD


class ProjectOut(BaseModel):
    id: int
    name: str
    region: str
    standard_type: str = "GB50500"
    language: str = "zh"
    currency: str = "CNY"


class DashboardSummaryOut(BaseModel):
    project_id: int
    boq_count: int
    unbound_count: int
    dirty_count: int
    validation_total: int
    validation_errors: int
    validation_warnings: int
    recent_audit_count: int
    recent_comment_count: int
