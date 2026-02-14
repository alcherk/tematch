from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User
from web.auth import create_jwt, verify_telegram_login
from web.deps import get_current_user, get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/telegram-login")
async def telegram_login(
    data: dict,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    from web.main import _settings

    if not verify_telegram_login(data, _settings.TG_BOT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid Telegram login")

    telegram_id = int(data["id"])

    stmt = select(User).where(User.telegram_id == telegram_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=401, detail="User not registered. Use /start in the bot first."
        )

    token = create_jwt(telegram_id=telegram_id, secret=_settings.WEB_JWT_SECRET)
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return {"ok": True, "telegram_id": telegram_id}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    from web.main import _settings

    return {
        "telegram_id": user.telegram_id,
        "interests": user.interests,
        "digest_cron": user.digest_cron,
        "is_admin": user.telegram_id == _settings.ADMIN_TELEGRAM_ID,
    }
