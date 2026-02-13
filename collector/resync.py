import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon import TelegramClient

from collector.channel_manager import get_active_channel_ids
from collector.handlers import handle_new_message
from core.models import Channel

logger = logging.getLogger(__name__)


def compute_resync_offset(
    last_fetched_at: Optional[datetime],
    max_hours: int,
    now: Optional[datetime] = None,
) -> datetime:
    if now is None:
        now = datetime.utcnow()
    floor = now - timedelta(hours=max_hours)
    if last_fetched_at is None:
        return floor
    return max(last_fetched_at, floor)


async def resync_channels(
    client: TelegramClient,
    session_factory: async_sessionmaker,
    embedding_buffer,
    max_hours: int = 72,
    batch_size: int = 100,
) -> None:
    async with session_factory() as session:
        active_tg_ids = await get_active_channel_ids(session)
        stmt = select(Channel).where(Channel.telegram_id.in_(active_tg_ids))
        channels = (await session.execute(stmt)).scalars().all()

    for channel in channels:
        offset_date = compute_resync_offset(channel.last_fetched_at, max_hours)
        logger.info(
            "Resync channel %s (id=%d) from %s",
            channel.title or channel.username,
            channel.telegram_id,
            offset_date,
        )

        count = 0
        async for msg in client.iter_messages(
            channel.telegram_id,
            offset_date=offset_date,
            limit=batch_size,
        ):
            if not msg.text or len(msg.text.strip()) < 20:
                continue

            async with session_factory() as session:
                await handle_new_message(
                    session=session,
                    channel_telegram_id=channel.telegram_id,
                    message_id=msg.id,
                    text=msg.text,
                    date=msg.date,
                    embedding_buffer=embedding_buffer,
                )
            count += 1

        logger.info("Resync channel %s: %d messages processed", channel.title, count)

        # Flush embeddings after each channel
        await embedding_buffer.flush()

        # Small delay to avoid Telegram rate limits
        await asyncio.sleep(1)
