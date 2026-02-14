from typing import Optional

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Channel, User, UserChannel

router = Router()


@router.message(F.forward_from_chat)
async def handle_forwarded(message: Message, session: AsyncSession):
    chat = message.forward_from_chat
    if chat.type != "channel":
        await message.answer("Это не канал. Перешли сообщение из канала.")
        return

    user = await _get_or_create_user(session, message.from_user.id)
    channel = await _get_or_create_channel(
        session, chat.id, chat.username, chat.title
    )
    await _link_user_channel(session, user.id, channel.id)
    await message.answer(f"Канал «{chat.title}» добавлен!")


@router.message(F.text.startswith("@"))
async def handle_channel_username(message: Message, session: AsyncSession):
    username = message.text.strip().lstrip("@")
    if not username:
        await message.answer("Отправь @username канала.")
        return

    user = await _get_or_create_user(session, message.from_user.id)
    channel = await _get_or_create_channel(
        session, telegram_id=None, username=username, title=username
    )
    await _link_user_channel(session, user.id, channel.id)
    await message.answer(
        f"Канал @{username} добавлен! Collector начнёт сбор при следующем цикле."
    )


async def _get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def _get_or_create_channel(
    session: AsyncSession,
    telegram_id: Optional[int],
    username: Optional[str],
    title: Optional[str],
) -> Channel:
    if telegram_id is not None:
        stmt = select(Channel).where(Channel.telegram_id == telegram_id)
    else:
        stmt = select(Channel).where(Channel.username == username)
    result = await session.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        channel = Channel(telegram_id=telegram_id, username=username, title=title)
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
    return channel


async def _link_user_channel(
    session: AsyncSession, user_id: int, channel_id: int
):
    stmt = select(UserChannel).where(
        UserChannel.user_id == user_id, UserChannel.channel_id == channel_id
    )
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        session.add(UserChannel(user_id=user_id, channel_id=channel_id))
        await session.commit()
