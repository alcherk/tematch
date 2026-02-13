import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.content_hash import compute_content_hash
from core.embeddings import EmbeddingService
from core.models import Channel, Message

logger = logging.getLogger(__name__)


async def handle_new_message(
    session: AsyncSession,
    embedding_service: EmbeddingService,
    channel_telegram_id: int,
    message_id: int,
    text: str,
    date: datetime,
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

    # Generate embedding
    try:
        embedding = await embedding_service.embed_text(text)
    except Exception:
        logger.exception("Embedding failed for message %s", message_id)
        embedding = None

    content_hash = compute_content_hash(text)

    msg = Message(
        channel_id=channel.id,
        telegram_msg_id=message_id,
        text=text,
        date=date,
        embedding=embedding,
        content_hash=content_hash,
    )
    session.add(msg)
    await session.commit()

    channel.last_fetched_at = datetime.utcnow()
    await session.commit()
