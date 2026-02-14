from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Channel, Message

MAX_TEXT_LEN = 4000
MAX_THREAD_MSG_LEN = 300


def generate_message_link(
    channel: Channel, telegram_msg_id: int
) -> Optional[str]:
    if channel.username:
        return f"https://t.me/{channel.username}/{telegram_msg_id}"
    if channel.telegram_id:
        return f"https://t.me/c/{channel.telegram_id}/{telegram_msg_id}"
    return None


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def format_recommendation(
    msg: Message,
    channel: Channel,
    score: float,
    thread_messages: Optional[dict[str, list[Message]]],
) -> str:
    parts: list = []

    # Header with score + link
    link = generate_message_link(channel, msg.telegram_msg_id)
    header = f"📌 Рекомендация (score: {score:.2f})"
    if link:
        header += f"\n🔗 {link}"
    parts.append(header)

    # Thread parents (context before main message)
    if thread_messages and thread_messages.get("parents"):
        parts.append("\n↩️ Контекст треда:")
        for parent in thread_messages["parents"]:
            parts.append(f"  └ {_truncate(parent.text, MAX_THREAD_MSG_LEN)}")

    # Main message text
    parts.append(f"\n{_truncate(msg.text, MAX_TEXT_LEN)}")

    # Thread children (replies after main message)
    if thread_messages and thread_messages.get("children"):
        parts.append("\n💬 Ответы:")
        for child in thread_messages["children"]:
            parts.append(f"  └ {_truncate(child.text, MAX_THREAD_MSG_LEN)}")

    return "\n".join(parts)


async def fetch_thread_context(
    session: AsyncSession,
    msg: Message,
    max_depth: int = 5,
) -> Optional[dict[str, list[Message]]]:
    if not hasattr(msg, "reply_to_msg_id") or msg.reply_to_msg_id is None:
        # Check for children even if this message isn't a reply itself
        children_stmt = select(Message).where(
            Message.channel_id == msg.channel_id,
            Message.reply_to_msg_id == msg.telegram_msg_id,
        )
        children = (await session.execute(children_stmt)).scalars().all()
        if not children:
            return None
        return {"parents": [], "children": list(children)}

    # Walk up parents
    parents: list = []
    current = msg
    for _ in range(max_depth):
        if current.reply_to_msg_id is None:
            break
        parent_stmt = select(Message).where(
            Message.channel_id == msg.channel_id,
            Message.telegram_msg_id == current.reply_to_msg_id,
        )
        parent = (await session.execute(parent_stmt)).scalar_one_or_none()
        if not parent:
            break
        parents.append(parent)
        current = parent

    parents.reverse()  # oldest first

    # Fetch children (direct replies to this message)
    children_stmt = select(Message).where(
        Message.channel_id == msg.channel_id,
        Message.reply_to_msg_id == msg.telegram_msg_id,
    )
    children = (await session.execute(children_stmt)).scalars().all()

    if not parents and not children:
        return None

    return {"parents": parents, "children": list(children)}
