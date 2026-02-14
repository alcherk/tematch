"""Tests for text_html handling in collector."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.tl.types import MessageEntityBold, MessageEntityItalic

from collector.handlers import handle_new_message


def _mock_session(channel=None, msg_exists=False):
    session = AsyncMock()
    # session.add is synchronous in real SQLAlchemy — use MagicMock to avoid
    # unawaited-coroutine warnings when running with -W error.
    session.add = MagicMock()
    ch_result = MagicMock()
    ch_result.scalar_one_or_none.return_value = channel
    exists_result = MagicMock()
    exists_result.scalar_one_or_none.return_value = 1 if msg_exists else None
    session.execute.side_effect = [ch_result, exists_result]
    return session


def _make_channel(id=5):
    ch = MagicMock()
    ch.id = id
    ch.last_fetched_at = None
    return ch


@pytest.mark.asyncio
async def test_handle_new_message_stores_text_html():
    """When entities are provided, text_html should be set."""
    ch = _make_channel()
    session = _mock_session(channel=ch)

    entities = [MessageEntityBold(offset=0, length=5)]
    await handle_new_message(
        session=session,
        channel_telegram_id=123,
        message_id=1,
        text="Hello world test message",
        date=datetime(2026, 2, 14),
        entities=entities,
    )

    added_msg = session.add.call_args[0][0]
    assert added_msg.text_html is not None
    assert "<strong>" in added_msg.text_html


@pytest.mark.asyncio
async def test_handle_new_message_no_entities_no_html():
    """When no entities provided, text_html should be None."""
    ch = _make_channel()
    session = _mock_session(channel=ch)

    await handle_new_message(
        session=session,
        channel_telegram_id=123,
        message_id=1,
        text="Plain text message here",
        date=datetime(2026, 2, 14),
    )

    added_msg = session.add.call_args[0][0]
    assert added_msg.text_html is None


@pytest.mark.asyncio
async def test_handle_existing_message_backfills_html():
    """When message already exists but text_html is NULL, update it."""
    ch = _make_channel()
    session = AsyncMock()

    ch_result = MagicMock()
    ch_result.scalar_one_or_none.return_value = ch
    exists_result = MagicMock()
    exists_result.scalar_one_or_none.return_value = 1
    msg_obj = MagicMock()
    msg_obj.text_html = None
    msg_result = MagicMock()
    msg_result.scalar_one_or_none.return_value = msg_obj

    session.execute.side_effect = [ch_result, exists_result, msg_result]

    entities = [MessageEntityItalic(offset=0, length=5)]
    await handle_new_message(
        session=session,
        channel_telegram_id=123,
        message_id=1,
        text="Hello world test message",
        date=datetime(2026, 2, 14),
        entities=entities,
    )

    assert msg_obj.text_html is not None
    assert "<em>" in msg_obj.text_html
