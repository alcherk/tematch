from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.embeddings import EmbeddingService
from core.models import User

router = Router()


@router.message(Command("interests"))
async def cmd_interests(message: Message, session: AsyncSession, embedding_service: EmbeddingService):
    text = message.text.replace("/interests", "").strip()
    if not text:
        await message.answer(
            "Опиши свои интересы после команды.\n"
            "Например: /interests ML, криптография, инди-игры, космос"
        )
        return

    stmt = select(User).where(User.telegram_id == message.from_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        await message.answer("Сначала используй /start")
        return

    user.interests = text
    result = await embedding_service.embed_text(text)
    user.interests_embedding = result.embeddings[0]
    await session.commit()
    await message.answer(f"Интересы обновлены: {text}")


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, session: AsyncSession):
    text = message.text.replace("/schedule", "").strip()
    if not text:
        await message.answer(
            "Укажи расписание в cron-формате.\n"
            "Например: /schedule 0 9 * * * (каждый день в 9:00)\n"
            "Или: /schedule off (отключить)"
        )
        return

    stmt = select(User).where(User.telegram_id == message.from_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        await message.answer("Сначала используй /start")
        return

    user.digest_cron = text if text != "off" else None
    await session.commit()
    if text == "off":
        await message.answer("Автодайджест отключён.")
    else:
        await message.answer(f"Расписание обновлено: {text}")
