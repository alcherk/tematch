from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types import Message as TgMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import feedback_keyboard
from core.models import Message as MsgModel
from core.models import Recommendation, User, UserChannel
from core.recommender import Recommender, compute_window_start

router = Router()


@router.message(Command("digest"))
async def cmd_digest(
    message: TgMessage, session: AsyncSession, recommender: Recommender
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
    )

    if not ranked:
        await message.answer(
            "Пока нет сообщений для рекомендаций. "
            "Подожди, пока collector соберёт контент."
        )
        return

    for item in ranked:
        msg = await session.get(MsgModel, item["message_id"])
        if not msg:
            continue

        rec = Recommendation(
            user_id=user.id, message_id=msg.id, score=item["score"], delivered=True
        )
        session.add(rec)
        await session.commit()
        await session.refresh(rec)

        text = f"📌 *Рекомендация* (score: {item['score']:.2f})\n\n{msg.text[:4000]}"
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
