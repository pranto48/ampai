"""Shared FastAPI authentication dependencies for AmpAI routers."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from pydantic import BaseModel

# ── JWT configuration ─────────────────────────────────────────────────────────
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_MINUTES: int = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
JWT_REMEMBER_ME_DAYS: int = int(os.getenv("JWT_REMEMBER_ME_DAYS", "30"))


# ── User context model ────────────────────────────────────────────────────────
class UserContext(BaseModel):
    username: str
    role: str


# ── JWT helpers ───────────────────────────────────────────────────────────────


def _create_access_token(
    data: dict,
    expiry_minutes: Optional[int] = None,
) -> str:
    """Create a signed JWT access token."""
    payload = data.copy()
    exp_minutes = int(expiry_minutes or JWT_EXPIRY_MINUTES)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=max(1, exp_minutes))
    payload.update({"exp": expiry})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _get_current_user(access_token: Optional[str] = None) -> UserContext:
    """Decode and validate a JWT token, returning a UserContext."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or role not in {"admin", "user"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return UserContext(username=username, role=role)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


# ── FastAPI dependency helpers ────────────────────────────────────────────────


def get_current_user_from_cookie(request: Request) -> UserContext:
    """Extract JWT from Authorization header or cookie and validate it."""
    auth_header = request.headers.get("Authorization", "")
    token: Optional[str] = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("access_token")
    return _get_current_user(token)


def require_authenticated_user(
    current_user: UserContext = Depends(get_current_user_from_cookie),
) -> UserContext:
    """Dependency: any authenticated user (admin or user)."""
    return current_user


def require_admin_user(
    current_user: UserContext = Depends(get_current_user_from_cookie),
) -> UserContext:
    """Dependency: admin-only access."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
