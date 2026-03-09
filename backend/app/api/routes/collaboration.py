from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.comment import Comment
from app.models.project_member import ProjectMember
from app.schemas.collaboration import CommentCreate, CommentOut, MemberCreate, MemberOut

router = APIRouter(tags=["collaboration"])


# --- Members ---

@router.post("/projects/{project_id}/members", response_model=MemberOut)
def add_member(
    project_id: int,
    payload: MemberCreate,
    db: Session = Depends(get_db),
) -> MemberOut:
    m = ProjectMember(
        project_id=project_id,
        user_name=payload.user_name,
        role=payload.role,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return MemberOut(id=m.id, project_id=m.project_id, user_name=m.user_name, role=m.role)


@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
def list_members(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    rows = db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()
    return [MemberOut(id=r.id, project_id=r.project_id, user_name=r.user_name, role=r.role) for r in rows]


# --- Comments ---

@router.post("/projects/{project_id}/comments", response_model=CommentOut)
def add_comment(
    project_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
) -> CommentOut:
    c = Comment(
        project_id=project_id,
        boq_item_id=payload.boq_item_id,
        author=payload.author,
        content=payload.content,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _comment_out(c)


@router.get("/projects/{project_id}/comments", response_model=list[CommentOut])
def list_comments(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    rows = (
        db.query(Comment)
        .filter(Comment.project_id == project_id)
        .order_by(Comment.id.desc())
        .all()
    )
    return [_comment_out(r) for r in rows]


def _comment_out(c: Comment) -> CommentOut:
    return CommentOut(
        id=c.id,
        project_id=c.project_id,
        boq_item_id=c.boq_item_id,
        author=c.author,
        content=c.content,
        created_at=c.created_at,
    )
