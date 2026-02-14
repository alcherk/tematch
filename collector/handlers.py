import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.content_hash import compute_content_hash
from core.models import Channel, Message

logger = logging.getLogger(__name__)


async def handle_new_message(
    session: AsyncSession,
    channel_telegram_id: int,
    message_id: int,
    text: str,
    date: datetime,
    embedding_buffer=None,
    reply_to_msg_id=None,
    has_media: bool = False,
):
    if not text or len(text.strip()) < 20:
        return

    # Find channel in DB
    stmt = select(Channel).where(Channel.telegram_id == channel_telegram_id)
    result = await session.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        return

    # Check if message already exists
    exists_stmt = select(Message.id).where(
        Message.channel_id == channel.id,
        Message.telegram_msg_id == message_id,
    )
    exists = (await session.execute(exists_stmt)).scalar_one_or_none()
    if exists:
        return

    content_hash = compute_content_hash(text)

    # Strip timezone — DB column is TIMESTAMP WITHOUT TIME ZONE
    naive_date = date.replace(tzinfo=None) if date and date.tzinfo else date

    msg = Message(
        channel_id=channel.id,
        telegram_msg_id=message_id,
        text=text,
        date=naive_date,
        content_hash=content_hash,
        reply_to_msg_id=reply_to_msg_id,
        has_media=has_media,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)

    # Add to embedding buffer for batched processing
    if embedding_buffer is not None:
        embedding_buffer.add(message_id=msg.id, text=text)

    channel.last_fetched_at = datetime.utcnow()
    await session.commit()
