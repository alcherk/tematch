from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Message, Recommendation, User
from web.deps import get_current_user, get_session

router = APIRouter(prefix="/api/users/me/digests", tags=["digests"])


@router.get("")
async def list_digests(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Recommendation, Message.text)
        .join(Message, Message.id == Recommendation.message_id)
        .where(
            Recommendation.user_id == user.id,
            Recommendation.delivered.is_(True),
        )
        .order_by(Recommendation.created_at.desc())
        .limit(50)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.Recommendation.id,
            "score": r.Recommendation.score,
            "feedback": r.Recommendation.feedback,
            "created_at": r.Recommendation.created_at.isoformat(),
            "text_preview": r.text[:200] if r.text else "",
        }
        for r in rows
    ]
