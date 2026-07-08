from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from joinable_core.settings import get_settings
from jose import JWTError, jwt
from pydantic import BaseModel

security = HTTPBearer(auto_error=False)


class AuthUser(BaseModel):
    id: UUID
    email: str | None = None


def _decode_token(token: str) -> AuthUser:
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not configured",
        )
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return AuthUser(id=UUID(sub), email=payload.get("email"))
    except (JWTError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> AuthUser | None:
    if credentials is None:
        return None
    return _decode_token(credentials.credentials)


async def get_required_user(
    user: Annotated[AuthUser | None, Depends(get_optional_user)],
) -> AuthUser:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


async def get_admin_user(user: Annotated[AuthUser, Depends(get_required_user)]) -> AuthUser:
    settings = get_settings()
    email = (user.email or "").lower()
    if email not in settings.admin_email_list:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
