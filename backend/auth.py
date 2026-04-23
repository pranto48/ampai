import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserContext(BaseModel):
    username: str
    role: Literal["admin", "user"]


class UserLoginResponse(BaseModel):
    username: str
    role: Literal["admin", "user"]


class AuthState(BaseModel):
    user: Optional[UserContext] = None


def _build_user_store() -> Dict[str, Dict[str, str]]:
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    user_username = os.getenv("USER_USERNAME", "user")
    user_password = os.getenv("USER_PASSWORD", "user123")
    return {
        admin_username: {
            "role": "admin",
            "password_hash": pwd_context.hash(admin_password),
        },
        user_username: {
            "role": "user",
            "password_hash": pwd_context.hash(user_password),
        },
    }


USERS = _build_user_store()


def _create_access_token(data: Dict[str, str]) -> str:
    payload = data.copy()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES)
    payload.update({"exp": expiry})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_access_token(access_token: Optional[str]) -> UserContext:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or role not in {"admin", "user"}:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return UserContext(username=username, role=role)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


async def auth_context_middleware(request: Request, call_next):
    token = request.cookies.get("access_token")
    request.state.auth = AuthState(user=None)
    if token:
        try:
            request.state.auth.user = _decode_access_token(token)
        except HTTPException:
            request.state.auth.user = None
    return await call_next(request)


def require_authenticated_user(request: Request) -> UserContext:
    auth_state: AuthState = getattr(request.state, "auth", AuthState())
    if auth_state.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return auth_state.user


def require_admin_user(current_user: UserContext = Depends(require_authenticated_user)) -> UserContext:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserLoginResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = USERS.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = _create_access_token({"sub": form_data.username, "role": user["role"]})
    response = Response(
        content=UserLoginResponse(username=form_data.username, role=user["role"]).model_dump_json(),
        media_type="application/json",
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=JWT_EXPIRY_MINUTES * 60,
    )
    return response


@router.post("/logout")
def logout():
    response = Response(content='{"status":"success"}', media_type="application/json")
    response.delete_cookie("access_token")
    return response


@router.get("/me", response_model=UserContext)
def auth_me(current_user: UserContext = Depends(require_authenticated_user)):
    return current_user
