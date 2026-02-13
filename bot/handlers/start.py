from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=message.from_user.id)
        session.add(user)
        await session.commit()
        await message.answer(
            "Привет! Я Tematch — подберу интересные сообщения из твоих каналов.\n\n"
            "Для начала:\n"
            "1. Перешли мне сообщение из канала или отправь @channel_name\n"
            "2. Настрой интересы: /interests\n"
            "3. Получи рекомендации: /digest"
        )
    else:
        await message.answer(
            "С возвращением! Используй /digest для рекомендаций "
            "или перешли сообщение для добавления канала."
        )
