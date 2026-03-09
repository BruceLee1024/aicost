from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.validation import ValidationIssueOut, ValidationReport
from app.services.validation_service import Severity, validate_project

router = APIRouter(tags=["validation"])


@router.get(
    "/projects/{project_id}/validation-issues",
    response_model=ValidationReport,
)
def get_validation_issues(
    project_id: int,
    db: Session = Depends(get_db),
) -> ValidationReport:
    """Run validation rules and return all issues for a project."""
    issues = validate_project(project_id=project_id, db=db)
    return ValidationReport(
        project_id=project_id,
        total_issues=len(issues),
        errors=sum(1 for i in issues if i.severity == Severity.ERROR),
        warnings=sum(1 for i in issues if i.severity == Severity.WARNING),
        issues=[
            ValidationIssueOut(
                code=i.code,
                severity=i.severity.value,
                boq_item_id=i.boq_item_id,
                message=i.message,
                suggestion=i.suggestion,
            )
            for i in issues
        ],
    )
