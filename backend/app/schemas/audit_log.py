from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    project_id: int
    actor: str
    action: str
    resource_type: str
    resource_id: int | None
    before_json: str | None
    after_json: str | None
    timestamp: str
