from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Channel, Message

MAX_TEXT_LEN = 4000
MAX_THREAD_MSG_LEN = 300
MAX_BODY_LEN = 600
MAX_THREAD_SNIPPET_LEN = 200
MAX_PAGE_CHARS = 4000


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


def html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class DigestItem:
    index: int           # 1-based position
    msg: Message
    channel: Channel
    score: float
    rec_id: int          # Recommendation ID for voting
    thread: Optional[dict] = None


def _format_single_item(item: DigestItem) -> str:
    parts: list[str] = []

    # Header: number + channel + score
    header = f"<b>{item.index}.</b> {html_escape(item.channel.title or '')} (score: {item.score:.2f})"
    parts.append(header)

    # Link (with image indicator when media is present)
    link = generate_message_link(item.channel, item.msg.telegram_msg_id)
    if link:
        has_media = getattr(item.msg, "has_media", False)
        icon = "🔗🖼" if has_media else "🔗"
        parts.append(f'<a href="{link}">{icon} Источник</a>')

    # Thread parents (context before)
    if item.thread and item.thread.get("parents"):
        parts.append("↩️ <i>Контекст:</i>")
        for parent in item.thread["parents"]:
            parts.append(f"  └ {html_escape(_truncate(parent.text, MAX_THREAD_SNIPPET_LEN))}")

    # Body
    parts.append(html_escape(_truncate(item.msg.text, MAX_BODY_LEN)))

    # Thread children (replies after)
    if item.thread and item.thread.get("children"):
        parts.append("💬 <i>Ответы:</i>")
        for child in item.thread["children"]:
            parts.append(f"  └ {html_escape(_truncate(child.text, MAX_THREAD_SNIPPET_LEN))}")

    return "\n".join(parts)


def format_digest_page(items: list[DigestItem]) -> str:
    sections = [_format_single_item(item) for item in items]
    return "\n\n———\n\n".join(sections)


def split_digest_pages(items: list[DigestItem]) -> list[list[DigestItem]]:
    pages: list[list[DigestItem]] = []
    current_page: list[DigestItem] = []
    current_len = 0

    for item in items:
        item_text = _format_single_item(item)
        # Account for divider between items
        divider_len = len("\n\n———\n\n") if current_page else 0
        new_len = current_len + divider_len + len(item_text)

        if current_page and new_len > MAX_PAGE_CHARS:
            pages.append(current_page)
            current_page = [item]
            current_len = len(item_text)
        else:
            current_page.append(item)
            current_len = new_len

    if current_page:
        pages.append(current_page)

    return pages


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
