from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Message, Recommendation, User
from web.deps import get_current_user, get_session

router = APIRouter(prefix="/api/users/me/digests", tags=["digests"])


class FeedbackBody(BaseModel):
    feedback: str


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


@router.patch("/{rec_id}/feedback")
async def update_feedback(
    rec_id: int,
    body: FeedbackBody,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if body.feedback not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="feedback must be 'like' or 'dislike'")

    rec = await session.get(Recommendation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    from web.main import _settings

    is_admin = user.telegram_id == _settings.ADMIN_TELEGRAM_ID
    if rec.user_id != user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Not your recommendation")

    rec.feedback = body.feedback
    await session.commit()
    return {"ok": True, "feedback": rec.feedback}
