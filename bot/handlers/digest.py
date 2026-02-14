from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types import Message as TgMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.formatters import fetch_thread_context, format_recommendation
from bot.keyboards import feedback_keyboard
from core.config import Settings
from core.models import Message as MsgModel
from core.models import Recommendation, User, UserChannel
from core.recommender import Recommender, compute_window_start

router = Router()


async def count_digests_today(session: AsyncSession, user_id: int) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(func.distinct(
        func.date_trunc("minute", Recommendation.created_at)
    ))).where(
        Recommendation.user_id == user_id,
        Recommendation.delivered.is_(True),
        Recommendation.created_at >= today_start,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() or 0


@router.message(Command("digest"))
async def cmd_digest(
    message: TgMessage, session: AsyncSession, recommender: Recommender,
    settings: Settings,
):
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        await message.answer("Сначала используй /start")
        return

    if not user.interests:
        await message.answer("Сначала настрой интересы: /interests <описание>")
        return

    # Get user's channel IDs
    ch_stmt = select(UserChannel.channel_id).where(UserChannel.user_id == user.id)
    channel_ids = (await session.execute(ch_stmt)).scalars().all()
    if not channel_ids:
        await message.answer(
            "Добавь каналы: перешли сообщение из канала или отправь @channel_name"
        )
        return

    is_admin = user.telegram_id == settings.ADMIN_TELEGRAM_ID

    # Rate limit: per-user digest cap (skip for admin)
    if not is_admin:
        digest_count = await count_digests_today(session, user.id)
        if digest_count >= 3:
            await message.answer(
                f"Лимит дайджестов на сегодня: {digest_count}/3. Попробуй завтра."
            )
            return

    # Rate limit: global token budget (skip for admin)
    if not is_admin:
        from core.llm_usage import get_daily_token_total

        daily_tokens = await get_daily_token_total(session)
        if daily_tokens >= 500_000:
            await message.answer("Дневной лимит токенов исчерпан. Попробуй завтра.")
            return

    await message.answer("Подбираю рекомендации...")

    window = compute_window_start(
        last_digest_at=user.last_digest_at,
        max_hours=72,
    )

    ranked = await recommender.recommend(
        session=session,
        user_id=user.id,
        interests=user.interests,
        channel_ids=list(channel_ids),
        window_start=window,
        interests_embedding=user.interests_embedding,
    )

    if not ranked:
        await message.answer(
            "Пока нет сообщений для рекомендаций. "
            "Подожди, пока collector соберёт контент."
        )
        return

    for item in ranked:
        stmt = (
            select(MsgModel)
            .where(MsgModel.id == item["message_id"])
            .options(selectinload(MsgModel.channel))
        )
        msg = (await session.execute(stmt)).scalar_one_or_none()
        if not msg:
            continue

        thread = await fetch_thread_context(session, msg)

        rec = Recommendation(
            user_id=user.id, message_id=msg.id, score=item["score"], delivered=True
        )
        session.add(rec)
        await session.commit()
        await session.refresh(rec)

        text = format_recommendation(msg, msg.channel, item["score"], thread)
        await message.answer(text, reply_markup=feedback_keyboard(rec.id))

    user.last_digest_at = datetime.utcnow()
    await session.commit()


@router.callback_query(F.data.startswith("fb:"))
async def handle_feedback(callback: CallbackQuery, session: AsyncSession):
    _, action, rec_id = callback.data.split(":")
    rec = await session.get(Recommendation, int(rec_id))
    if rec:
        rec.feedback = action
        await session.commit()
    await callback.answer("Спасибо за отзыв!")
