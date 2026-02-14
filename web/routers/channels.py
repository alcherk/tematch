from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Channel, Message, User, UserChannel
from web.deps import get_current_user, get_session

router = APIRouter(prefix="/api/users/me/channels", tags=["channels"])


@router.get("")
async def list_channels(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(
            Channel.id,
            Channel.title,
            Channel.username,
            UserChannel.added_at,
            func.count(Message.id).label("message_count"),
        )
        .join(UserChannel, UserChannel.channel_id == Channel.id)
        .outerjoin(Message, Message.channel_id == Channel.id)
        .where(UserChannel.user_id == user.id)
        .group_by(Channel.id, UserChannel.added_at)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "title": r.title or r.username,
            "username": r.username,
            "added_at": r.added_at.isoformat() if r.added_at else None,
            "message_count": r.message_count,
        }
        for r in rows
    ]


@router.delete("/{channel_id}")
async def unsubscribe(
    channel_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    stmt = select(UserChannel).where(
        UserChannel.user_id == user.id,
        UserChannel.channel_id == channel_id,
    )
    link = (await session.execute(stmt)).scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await session.delete(link)
    await session.commit()
    return {"ok": True}
