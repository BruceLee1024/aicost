"""Authentication API — login, register, me."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    hash_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ──

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str
    display_name: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str


# ── Auth dependency ──

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User | None:
    """Extract current user from Authorization header. Returns None if no/invalid token.

    This is a soft dependency — routes can work without auth in dev mode.
    Use `require_role()` for strict enforcement.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = int(payload.get("sub", 0))
    return db.query(User).filter(User.id == user_id, User.is_active == 1).first()


def require_role(*allowed_roles: str):
    """FastAPI dependency factory that enforces role-based access."""
    def _check(
        authorization: Optional[str] = Header(None),
        db: Session = Depends(get_db),
    ) -> User:
        user = get_current_user(authorization=authorization, db=db)
        if not user:
            raise HTTPException(status_code=401, detail="认证失败，请登录")
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"权限不足，需要角色: {', '.join(allowed_roles)}")
        return user
    return _check


# ── Endpoints ──

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.display_name,
    )


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        role="viewer",  # New users default to viewer
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.display_name,
    )


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(require_role("owner", "editor", "viewer"))) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )
