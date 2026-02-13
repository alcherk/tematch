import logging
from typing import Optional

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.keyboards import feedback_keyboard
from core.models import Message, Recommendation, UserChannel
from core.recommender import Recommender

logger = logging.getLogger(__name__)


def parse_cron(cron_str: Optional[str]) -> Optional[dict]:
    if not cron_str:
        return None
    parts = cron_str.strip().split()
    if len(parts) != 5:
        return None
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


async def send_digest_to_user(
    bot: Bot,
    session_factory: async_sessionmaker,
    recommender: Recommender,
    user_id: int,
    telegram_id: int,
    interests: str,
):
    async with session_factory() as session:
        ch_stmt = select(UserChannel.channel_id).where(
            UserChannel.user_id == user_id
        )
        channel_ids = (await session.execute(ch_stmt)).scalars().all()
        if not channel_ids:
            return

        ranked = await recommender.recommend(
            session=session,
            user_id=user_id,
            interests=interests,
            channel_ids=list(channel_ids),
        )

        if not ranked:
            return

        await bot.send_message(telegram_id, "📬 Твой дайджест готов!")

        for item in ranked:
            msg = await session.get(Message, item["message_id"])
            if not msg:
                continue

            rec = Recommendation(
                user_id=user_id,
                message_id=msg.id,
                score=item["score"],
                delivered=True,
            )
            session.add(rec)
            await session.commit()
            await session.refresh(rec)

            text = (
                f"📌 *Рекомендация* (score: {item['score']:.2f})\n\n"
                f"{msg.text[:4000]}"
            )
            await bot.send_message(
                telegram_id, text, reply_markup=feedback_keyboard(rec.id)
            )
