"""E2E tests for content-hash deduplication across channels."""

from datetime import datetime

import pytest
from sqlalchemy import select

from core.content_hash import compute_content_hash
from core.models import Channel, Message
from core.recommender import deduplicate_candidates


@pytest.mark.asyncio
async def test_same_text_different_channels_deduped(session):
    """Feature 10: identical posts across channels keep only the earliest."""
    ch1 = Channel(telegram_id=700_001, title="News A")
    ch2 = Channel(telegram_id=700_002, title="News B")
    session.add_all([ch1, ch2])
    await session.commit()

    text = "Breaking: major ML breakthrough announced today by researchers"
    content_hash = compute_content_hash(text)

    msg1 = Message(
        channel_id=ch1.id, telegram_msg_id=1, text=text,
        content_hash=content_hash, date=datetime(2026, 2, 13, 10, 0),
    )
    msg2 = Message(
        channel_id=ch2.id, telegram_msg_id=1, text=text,
        content_hash=content_hash, date=datetime(2026, 2, 13, 12, 0),
    )
    session.add_all([msg1, msg2])
    await session.commit()

    result = deduplicate_candidates([msg1, msg2])
    assert len(result) == 1
    assert result[0].id == msg1.id


@pytest.mark.asyncio
async def test_different_text_not_deduped(session):
    """Feature 10: different texts have different hashes, both survive."""
    ch = Channel(telegram_id=700_003, title="Mixed")
    session.add(ch)
    await session.commit()

    msg1 = Message(
        channel_id=ch.id, telegram_msg_id=10, text="First unique post about AI safety",
        content_hash=compute_content_hash("First unique post about AI safety"),
        date=datetime(2026, 2, 13, 10, 0),
    )
    msg2 = Message(
        channel_id=ch.id, telegram_msg_id=11, text="Second unique post about quantum computing",
        content_hash=compute_content_hash("Second unique post about quantum computing"),
        date=datetime(2026, 2, 13, 11, 0),
    )
    session.add_all([msg1, msg2])
    await session.commit()

    result = deduplicate_candidates([msg1, msg2])
    assert len(result) == 2


def test_content_hash_normalization():
    """Feature 10: hash is stable across whitespace/case variations."""
    h1 = compute_content_hash("Hello   World")
    h2 = compute_content_hash("hello world")
    h3 = compute_content_hash("  HELLO   WORLD  ")
    assert h1 == h2 == h3
    assert len(h1) == 64


@pytest.mark.asyncio
async def test_content_hash_stored_in_db(session):
    """Feature 10: content_hash column is populated on insert."""
    ch = Channel(telegram_id=700_004, title="HashTest")
    session.add(ch)
    await session.commit()

    text = "A sufficiently long message to pass validation"
    msg = Message(
        channel_id=ch.id, telegram_msg_id=20, text=text,
        content_hash=compute_content_hash(text),
        date=datetime(2026, 2, 13, 10, 0),
    )
    session.add(msg)
    await session.commit()

    stmt = select(Message).where(Message.id == msg.id)
    found = (await session.execute(stmt)).scalar_one()
    assert found.content_hash is not None
    assert len(found.content_hash) == 64
