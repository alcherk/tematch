import logging
from typing import Optional

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from bot.formatters import (
    DigestItem,
    fetch_thread_context,
    format_digest_page,
    split_digest_pages,
)
from bot.keyboards import digest_keyboard
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

        # Collect all recommendations and build DigestItems
        digest_items: list = []
        idx = 1
        for item in ranked:
            stmt = (
                select(Message)
                .where(Message.id == item["message_id"])
                .options(selectinload(Message.channel))
            )
            msg = (await session.execute(stmt)).scalar_one_or_none()
            if not msg:
                continue

            thread = await fetch_thread_context(session, msg)

            rec = Recommendation(
                user_id=user_id,
                message_id=msg.id,
                score=item["score"],
                delivered=True,
            )
            session.add(rec)
            await session.flush()

            digest_items.append(DigestItem(
                index=idx, msg=msg, channel=msg.channel,
                score=item["score"], rec_id=rec.id, thread=thread,
            ))
            idx += 1

        await session.commit()

        # Send paginated digest
        for page_items in split_digest_pages(digest_items):
            text = format_digest_page(page_items)
            await bot.send_message(
                telegram_id, text,
                parse_mode="HTML", reply_markup=digest_keyboard(page_items),
            )
