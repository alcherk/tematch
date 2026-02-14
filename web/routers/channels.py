from fastapi import APIRouter, Depends, HTTPException, Query
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


@router.get("/{channel_id}/messages")
async def channel_messages(
    channel_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # Verify subscription
    sub_stmt = select(UserChannel).where(
        UserChannel.user_id == user.id,
        UserChannel.channel_id == channel_id,
    )
    sub = (await session.execute(sub_stmt)).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Channel not in subscriptions")

    # Get channel info
    ch = (await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )).scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Total count
    count_stmt = select(func.count(Message.id)).where(Message.channel_id == channel_id)
    total = (await session.execute(count_stmt)).scalar_one()

    # Paginated messages with optional relevance
    offset = (page - 1) * per_page

    if user.interests_embedding is not None:
        stmt = (
            select(
                Message.id,
                Message.text,
                Message.text_html,
                Message.date,
                Message.has_media,
                (Message.embedding.isnot(None)).label("has_embedding"),
                (1 - Message.embedding.cosine_distance(user.interests_embedding)).label(
                    "relevance"
                ),
            )
            .where(Message.channel_id == channel_id)
            .order_by(Message.date.desc())
            .offset(offset)
            .limit(per_page)
        )
    else:
        stmt = (
            select(
                Message.id,
                Message.text,
                Message.text_html,
                Message.date,
                Message.has_media,
                (Message.embedding.isnot(None)).label("has_embedding"),
            )
            .where(Message.channel_id == channel_id)
            .order_by(Message.date.desc())
            .offset(offset)
            .limit(per_page)
        )

    rows = (await session.execute(stmt)).all()

    return {
        "channel": {
            "id": ch.id,
            "title": ch.title or ch.username,
            "username": ch.username,
        },
        "messages": [
            {
                "id": r.id,
                "text": r.text or "",
                "text_html": r.text_html if r.text_html else None,
                "date": r.date.isoformat() if r.date else None,
                "has_embedding": r.has_embedding,
                "relevance": round(r.relevance, 3)
                if hasattr(r, "relevance") and r.relevance is not None
                else None,
                "has_media": r.has_media,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


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
