from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User
from web.auth import decode_jwt


async def get_session():
    """Overridden at app startup with real session factory."""
    raise NotImplementedError


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    token: Optional[str] = Cookie(None, alias="auth_token"),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from web.main import _settings

    payload = decode_jwt(token, _settings.WEB_JWT_SECRET)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    stmt = select(User).where(User.telegram_id == payload["telegram_id"])
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    from web.main import _settings

    if user.telegram_id != _settings.ADMIN_TELEGRAM_ID:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
