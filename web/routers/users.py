from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User
from web.deps import get_current_user, get_session

router = APIRouter(prefix="/api/users", tags=["users"])


class UserUpdate(BaseModel):
    interests: Optional[str] = None
    digest_cron: Optional[str] = None


@router.get("/me")
async def get_profile(user: User = Depends(get_current_user)):
    return {
        "telegram_id": user.telegram_id,
        "interests": user.interests,
        "digest_cron": user.digest_cron,
        "last_digest_at": user.last_digest_at.isoformat() if user.last_digest_at else None,
        "created_at": user.created_at.isoformat(),
    }


@router.patch("/me")
async def update_profile(
    body: UserUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if body.interests is not None:
        user.interests = body.interests
    if body.digest_cron is not None:
        user.digest_cron = body.digest_cron if body.digest_cron != "off" else None
    await session.commit()
    return {"ok": True}
