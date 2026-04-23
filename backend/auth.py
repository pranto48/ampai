"""Lightweight auth module compatible with older Ampai imports.

This module intentionally avoids passlib/bcrypt so container boot cannot fail due
to bcrypt backend incompatibilities.
"""
from dataclasses import dataclass
from typing import Optional
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request

router = APIRouter(prefix="/api/auth", tags=["auth"])


@dataclass
class UserContext:
    username: str
    role: str
    token: str


USER_TOKEN = os.getenv("AMPAI_USER_TOKEN", "ampai-user")
ADMIN_TOKEN = os.getenv("AMPAI_ADMIN_TOKEN", "ampai-admin")


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return authorization.strip()


def _ctx_for_token(token: Optional[str]) -> Optional[UserContext]:
    if token == ADMIN_TOKEN:
        return UserContext(username="admin", role="admin", token=token)
    if token == USER_TOKEN:
        return UserContext(username="user", role="user", token=token)
    return None


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
def login(payload: dict):
    token = payload.get("token")
    ctx = _ctx_for_token(token)
    if not ctx:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"token": ctx.token, "role": ctx.role, "username": ctx.username}


@router.get("/whoami")
def whoami(user: UserContext = Depends(require_authenticated_user)):
    return {"username": user.username, "role": user.role}
