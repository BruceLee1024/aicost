from pydantic import BaseModel


class ValidationIssueOut(BaseModel):
    code: str
    severity: str
    boq_item_id: int | None
    message: str
    suggestion: str


class ValidationReport(BaseModel):
    project_id: int
    total_issues: int
    errors: int
    warnings: int
    issues: list[ValidationIssueOut]
