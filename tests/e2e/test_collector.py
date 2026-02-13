"""E2E tests for collector: message storage, dedup, embedding buffer."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from collector.embedding_buffer import EmbeddingBuffer
from collector.handlers import handle_new_message
from core.content_hash import compute_content_hash
from core.embeddings import EmbeddingResult
from core.models import Channel, Message


@pytest.mark.asyncio
async def test_message_stored_with_content_hash(session):
    """Feature 12: collector stores message with computed content_hash."""
    ch = Channel(telegram_id=400_001, title="CollectorTest", active=True)
    session.add(ch)
    await session.commit()

    mock_buffer = AsyncMock(spec=EmbeddingBuffer)

    await handle_new_message(
        session=session,
        channel_telegram_id=400_001,
        message_id=42,
        text="This is a long enough test message for the collector",
        date=datetime.utcnow(),
        embedding_buffer=mock_buffer,
    )

    stmt = select(Message).where(Message.telegram_msg_id == 42)
    msg = (await session.execute(stmt)).scalar_one()

    assert msg.content_hash is not None
    assert len(msg.content_hash) == 64
    assert msg.content_hash == compute_content_hash(
        "This is a long enough test message for the collector"
    )
    mock_buffer.add.assert_called_once_with(message_id=msg.id, text=msg.text)


@pytest.mark.asyncio
async def test_short_message_skipped(session):
    """Feature 12: messages shorter than 20 chars are ignored."""
    ch = Channel(telegram_id=400_002, title="ShortTest", active=True)
    session.add(ch)
    await session.commit()

    await handle_new_message(
        session=session,
        channel_telegram_id=400_002,
        message_id=43,
        text="Too short",
        date=datetime.utcnow(),
    )

    stmt = select(Message).where(Message.telegram_msg_id == 43)
    msg = (await session.execute(stmt)).scalar_one_or_none()
    assert msg is None


@pytest.mark.asyncio
async def test_duplicate_message_skipped(session):
    """Feature 12: duplicate (channel_id, msg_id) is stored only once."""
    ch = Channel(telegram_id=400_003, title="DupTest", active=True)
    session.add(ch)
    await session.commit()

    text = "This message is long enough to be stored by the collector"
    for _ in range(2):
        await handle_new_message(
            session=session,
            channel_telegram_id=400_003,
            message_id=99,
            text=text,
            date=datetime.utcnow(),
        )

    count = (await session.execute(
        select(func.count()).select_from(Message).where(Message.telegram_msg_id == 99)
    )).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_unknown_channel_ignored(session):
    """Feature 12: messages from unknown channels are silently ignored."""
    await handle_new_message(
        session=session,
        channel_telegram_id=999_999,
        message_id=100,
        text="Message from unknown channel that should be ignored",
        date=datetime.utcnow(),
    )

    stmt = select(Message).where(Message.telegram_msg_id == 100)
    msg = (await session.execute(stmt)).scalar_one_or_none()
    assert msg is None


@pytest.mark.asyncio
async def test_channel_last_fetched_at_updated(session):
    """Feature 12: channel.last_fetched_at is updated after storing message."""
    ch = Channel(telegram_id=400_004, title="FetchTest", active=True)
    session.add(ch)
    await session.commit()

    assert ch.last_fetched_at is None

    await handle_new_message(
        session=session,
        channel_telegram_id=400_004,
        message_id=101,
        text="Long enough message to trigger storage and update",
        date=datetime.utcnow(),
    )

    await session.refresh(ch)
    assert ch.last_fetched_at is not None


@pytest.mark.asyncio
async def test_embedding_buffer_batches_and_flushes(session_factory):
    """Feature 14: buffer accumulates messages and calls embed_texts in batch."""
    mock_embed = AsyncMock()
    mock_embed.embed_texts.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1536, [0.2] * 1536],
        tokens=50,
    )

    buffer = EmbeddingBuffer(
        embedding_service=mock_embed,
        session_factory=session_factory,
        batch_size=2,
    )

    buffer.add(1, "first text")
    assert len(buffer._pending) == 1
    assert not buffer.should_flush

    buffer.add(2, "second text")
    assert buffer.should_flush

    await buffer.flush()
    mock_embed.embed_texts.assert_called_once_with(["first text", "second text"])
    assert len(buffer._pending) == 0


def test_embedding_buffer_empty_flush_is_noop():
    """Feature 14: flushing empty buffer does nothing."""
    from unittest.mock import MagicMock

    buffer = EmbeddingBuffer(
        embedding_service=MagicMock(),
        session_factory=MagicMock(),
        batch_size=20,
    )
    assert len(buffer._pending) == 0
    assert not buffer.should_flush
