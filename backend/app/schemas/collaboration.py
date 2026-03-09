from pydantic import BaseModel


class MemberCreate(BaseModel):
    user_name: str
    role: str = "viewer"  # owner / editor / viewer


class MemberOut(BaseModel):
    id: int
    project_id: int
    user_name: str
    role: str


class CommentCreate(BaseModel):
    boq_item_id: int | None = None
    author: str
    content: str


class CommentOut(BaseModel):
    id: int
    project_id: int
    boq_item_id: int | None
    author: str
    content: str
    created_at: str
