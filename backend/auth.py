from dataclasses import dataclass
from typing import Optional
import os
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from database import verify_user_credentials, create_user, ensure_default_admin, list_users, set_user_role, delete_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/admin/users", tags=["users"])


@dataclass
class UserContext:
    user_id: int
    username: str
    role: str
    token: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class AdminCreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class AdminRoleUpdateRequest(BaseModel):
    role: str


# In-memory token store for lightweight deployments.
TOKEN_STORE: dict[str, dict] = {}


DEFAULT_ADMIN_USERNAME = os.getenv("AMPAI_DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("AMPAI_DEFAULT_ADMIN_PASSWORD", "admin123")


def bootstrap_default_admin():
    ensure_default_admin(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD)


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return authorization.strip()


def _ctx_for_token(token: Optional[str]) -> Optional[UserContext]:
    if not token:
        return None
    payload = TOKEN_STORE.get(token)
    if not payload:
        return None
    return UserContext(user_id=payload["id"], username=payload["username"], role=payload["role"], token=token)


async def auth_context_middleware(request: Request, call_next):
    token = _extract_token(request.headers.get("Authorization"))
    request.state.user = _ctx_for_token(token)
    return await call_next(request)


def require_authenticated_user(authorization: Optional[str] = Header(None)) -> UserContext:
    ctx = _ctx_for_token(_extract_token(authorization))
    if not ctx:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return ctx


def require_admin_user(user: UserContext = Depends(require_authenticated_user)) -> UserContext:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/login")
def login(payload: LoginRequest):
    user = verify_user_credentials(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_urlsafe(32)
    TOKEN_STORE[token] = user
    return {"token": token, "role": user["role"], "username": user["username"]}


@router.post("/register")
def register(payload: RegisterRequest):
    ok, reason = create_user(payload.username, payload.password, role="user")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    return {"status": "success"}


@router.get("/whoami")
def whoami(user: UserContext = Depends(require_authenticated_user)):
    return {"id": user.user_id, "username": user.username, "role": user.role}


@router.post("/logout")
def logout(user: UserContext = Depends(require_authenticated_user)):
    TOKEN_STORE.pop(user.token, None)
    return {"status": "success"}


@admin_router.get("")
def admin_list_users(_: UserContext = Depends(require_admin_user)):
    return {"users": list_users()}


@admin_router.post("")
def admin_create_user(payload: AdminCreateUserRequest, _: UserContext = Depends(require_admin_user)):
    ok, reason = create_user(payload.username, payload.password, role=payload.role)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    return {"status": "success"}


@admin_router.patch("/{user_id}/role")
def admin_update_user_role(user_id: int, payload: AdminRoleUpdateRequest, _: UserContext = Depends(require_admin_user)):
    if not set_user_role(user_id, payload.role):
        raise HTTPException(status_code=400, detail="Failed to update role")
    return {"status": "success"}


@admin_router.delete("/{user_id}")
def admin_delete_user(user_id: int, _: UserContext = Depends(require_admin_user)):
    if not delete_user(user_id):
        raise HTTPException(status_code=400, detail="Failed to delete user")
    return {"status": "success"}
