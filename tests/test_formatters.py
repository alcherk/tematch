from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.formatters import fetch_thread_context, format_recommendation, generate_message_link

# --- generate_message_link ---


def _make_channel(username=None, telegram_id=None):
    ch = MagicMock()
    ch.username = username
    ch.telegram_id = telegram_id
    return ch


def test_link_public_channel():
    ch = _make_channel(username="tech_news")
    assert generate_message_link(ch, 42) == "https://t.me/tech_news/42"


def test_link_private_channel():
    ch = _make_channel(telegram_id=1234567890)
    assert generate_message_link(ch, 7) == "https://t.me/c/1234567890/7"


def test_link_public_preferred_over_private():
    ch = _make_channel(username="pub", telegram_id=999)
    assert generate_message_link(ch, 1) == "https://t.me/pub/1"


def test_link_no_identifiers():
    ch = _make_channel()
    assert generate_message_link(ch, 1) is None


# --- format_recommendation ---


def _make_msg(text="Hello world", telegram_msg_id=10):
    msg = MagicMock()
    msg.text = text
    msg.telegram_msg_id = telegram_msg_id
    return msg


def test_format_basic():
    ch = _make_channel(username="chan")
    msg = _make_msg(text="Test message body")
    result = format_recommendation(msg, ch, score=0.85, thread_messages=None)
    assert "0.85" in result
    assert "https://t.me/chan/10" in result
    assert "Test message body" in result


def test_format_no_link():
    ch = _make_channel()
    msg = _make_msg(text="No link message")
    result = format_recommendation(msg, ch, score=0.5, thread_messages=None)
    assert "No link message" in result
    assert "0.50" in result
    assert "t.me" not in result


def test_format_with_thread_parents():
    ch = _make_channel(username="ch")
    msg = _make_msg(text="Main message")
    thread = {"parents": [_make_msg(text="Parent msg")], "children": []}
    result = format_recommendation(msg, ch, score=0.9, thread_messages=thread)
    assert "Parent msg" in result
    assert "Main message" in result


def test_format_with_thread_children():
    ch = _make_channel(username="ch")
    msg = _make_msg(text="Main message")
    thread = {"parents": [], "children": [_make_msg(text="Child reply")]}
    result = format_recommendation(msg, ch, score=0.9, thread_messages=thread)
    assert "Child reply" in result
    assert "Main message" in result


def test_format_truncates_long_text():
    ch = _make_channel(username="ch")
    msg = _make_msg(text="A" * 5000)
    result = format_recommendation(msg, ch, score=0.5, thread_messages=None)
    assert len(result) < 5000


def test_format_truncates_thread_context():
    ch = _make_channel(username="ch")
    msg = _make_msg(text="Main")
    long_parent = _make_msg(text="P" * 500)
    thread = {"parents": [long_parent], "children": []}
    result = format_recommendation(msg, ch, score=0.5, thread_messages=thread)
    # Thread context message should be truncated to ~300 chars
    lines = result.split("\n")
    parent_lines = [line for line in lines if "P" * 50 in line]
    for line in parent_lines:
        assert len(line) <= 320  # 300 + some prefix chars


# --- fetch_thread_context ---


def _make_db_msg(text="msg", telegram_msg_id=1, channel_id=10, reply_to_msg_id=None):
    msg = MagicMock()
    msg.text = text
    msg.telegram_msg_id = telegram_msg_id
    msg.channel_id = channel_id
    msg.reply_to_msg_id = reply_to_msg_id
    return msg


def _mock_result_scalar(value):
    """Mock for session.execute() that returns .scalar_one_or_none()"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_result_scalars(values):
    """Mock for session.execute() that returns .scalars().all()"""
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_fetch_thread_no_reply_no_children():
    msg = _make_db_msg(reply_to_msg_id=None)
    session = AsyncMock()
    session.execute.return_value = _mock_result_scalars([])

    result = await fetch_thread_context(session, msg)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_thread_no_reply_but_has_children():
    msg = _make_db_msg(reply_to_msg_id=None, telegram_msg_id=5)
    child = _make_db_msg(text="child reply", reply_to_msg_id=5)
    session = AsyncMock()
    session.execute.return_value = _mock_result_scalars([child])

    result = await fetch_thread_context(session, msg)
    assert result is not None
    assert result["parents"] == []
    assert len(result["children"]) == 1
    assert result["children"][0].text == "child reply"


@pytest.mark.asyncio
async def test_fetch_thread_with_parent():
    parent = _make_db_msg(text="parent", telegram_msg_id=1, reply_to_msg_id=None)
    msg = _make_db_msg(text="reply", telegram_msg_id=2, reply_to_msg_id=1)
    session = AsyncMock()
    # Call 1: find parent (scalar_one_or_none)
    # Call 2: find children of msg (scalars().all())
    session.execute.side_effect = [
        _mock_result_scalar(parent),
        _mock_result_scalars([]),
    ]

    result = await fetch_thread_context(session, msg)
    assert result is not None
    assert len(result["parents"]) == 1
    assert result["parents"][0].text == "parent"


@pytest.mark.asyncio
async def test_fetch_thread_depth_limit():
    """Chain of 7 messages, max_depth=3 should only walk up 3 parents."""
    msgs = [
        _make_db_msg(telegram_msg_id=i, reply_to_msg_id=i - 1 if i > 0 else None)
        for i in range(7)
    ]
    target = msgs[6]  # reply_to_msg_id=5

    session = AsyncMock()
    # Will walk: 6->5, 5->4, 4->3, then stop (max_depth=3)
    session.execute.side_effect = [
        _mock_result_scalar(msgs[5]),  # parent of 6
        _mock_result_scalar(msgs[4]),  # parent of 5
        _mock_result_scalar(msgs[3]),  # parent of 4
        _mock_result_scalars([]),      # children of 6
    ]

    result = await fetch_thread_context(session, target, max_depth=3)
    assert result is not None
    assert len(result["parents"]) == 3


@pytest.mark.asyncio
async def test_fetch_thread_missing_parent():
    """Parent message not in DB — should stop walking."""
    msg = _make_db_msg(reply_to_msg_id=99)
    session = AsyncMock()
    session.execute.side_effect = [
        _mock_result_scalar(None),     # parent not found
        _mock_result_scalars([]),      # children
    ]

    result = await fetch_thread_context(session, msg)
    assert result is None
