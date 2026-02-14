from datetime import datetime, timedelta
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery
from aiogram.types import Message as TgMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.formatters import (
    DigestItem,
    fetch_thread_context,
    format_digest_page,
    split_digest_pages,
)
from bot.keyboards import digest_keyboard
from core.config import Settings
from core.models import Channel, Recommendation, User, UserChannel
from core.models import Message as MsgModel
from core.recommender import Recommender, compute_window_start

router = Router()


async def count_digests_today(session: AsyncSession, user_id: int) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(func.distinct(
        func.date_trunc("minute", Recommendation.created_at)
    ))).where(
        Recommendation.user_id == user_id,
        Recommendation.delivered.is_(True),
        Recommendation.created_at >= today_start,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() or 0


async def _resolve_channel(
    session: AsyncSession, user_id: int, arg: str,
) -> Optional[Channel]:
    """Resolve channel arg to a Channel the user is subscribed to."""
    arg = arg.lstrip("@")
    stmt = (
        select(Channel)
        .join(UserChannel)
        .where(
            UserChannel.user_id == user_id,
            (Channel.username == arg)
            | (Channel.title == arg)
            | (Channel.title == f"channel_{arg}"),
        )
    )
    ch = (await session.execute(stmt)).scalar_one_or_none()
    if ch:
        return ch
    # Try telegram_id (bare or with -100 prefix)
    for candidate in [arg, f"-100{arg}"]:
        try:
            tid = int(candidate)
        except ValueError:
            continue
        stmt = (
            select(Channel)
            .join(UserChannel)
            .where(
                UserChannel.user_id == user_id,
                Channel.telegram_id == tid,
            )
        )
        ch = (await session.execute(stmt)).scalar_one_or_none()
        if ch:
            return ch
    return None


@router.message(Command("digest"))
async def cmd_digest(
    message: TgMessage, command: CommandObject, session: AsyncSession,
    recommender: Recommender, settings: Settings,
):
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        await message.answer("Сначала используй /start")
        return

    if not user.interests:
        await message.answer("Сначала настрой интересы: /interests <описание>")
        return

    # Parse optional channel argument: /digest @channel or /digest title
    channel_arg = (command.args or "").strip()

    # Get user's channel IDs
    ch_stmt = select(UserChannel.channel_id).where(UserChannel.user_id == user.id)
    all_channel_ids = (await session.execute(ch_stmt)).scalars().all()
    if not all_channel_ids:
        await message.answer(
            "Добавь каналы: перешли сообщение из канала или отправь @channel_name"
        )
        return

    # Resolve target channel if argument provided
    single_channel = False
    if channel_arg:
        target = await _resolve_channel(session, user.id, channel_arg)
        if not target:
            await message.answer("Канал не найден среди подписок.")
            return
        channel_ids = [target.id]
        single_channel = True
    else:
        channel_ids = list(all_channel_ids)

    is_admin = user.telegram_id == settings.ADMIN_TELEGRAM_ID

    # Rate limit: per-user digest cap (skip for admin)
    if not is_admin:
        digest_count = await count_digests_today(session, user.id)
        if digest_count >= 3:
            await message.answer(
                f"Лимит дайджестов на сегодня: {digest_count}/3. Попробуй завтра."
            )
            return

    # Rate limit: global token budget (skip for admin)
    if not is_admin:
        from core.llm_usage import get_daily_token_total

        daily_tokens = await get_daily_token_total(session)
        if daily_tokens >= 500_000:
            await message.answer("Дневной лимит токенов исчерпан. Попробуй завтра.")
            return

    await message.answer("Подбираю рекомендации...")

    if single_channel:
        # Full 72h window for per-channel digest, ignore last_digest_at
        window = datetime.utcnow() - timedelta(hours=72)
    else:
        window = compute_window_start(
            last_digest_at=user.last_digest_at,
            max_hours=72,
        )

    ranked = await recommender.recommend(
        session=session,
        user_id=user.id,
        interests=user.interests,
        channel_ids=channel_ids,
        window_start=window,
        interests_embedding=user.interests_embedding,
    )

    if not ranked:
        await message.answer(
            "Пока нет сообщений для рекомендаций. "
            "Подожди, пока collector соберёт контент."
        )
        return

    # Collect all recommendations and build DigestItems
    digest_items: list = []
    idx = 1
    for item in ranked:
        stmt = (
            select(MsgModel)
            .where(MsgModel.id == item["message_id"])
            .options(selectinload(MsgModel.channel))
        )
        msg = (await session.execute(stmt)).scalar_one_or_none()
        if not msg:
            continue

        thread = await fetch_thread_context(session, msg)

        rec = Recommendation(
            user_id=user.id, message_id=msg.id, score=item["score"], delivered=True
        )
        session.add(rec)
        await session.flush()

        digest_items.append(DigestItem(
            index=idx, msg=msg, channel=msg.channel,
            score=item["score"], rec_id=rec.id, thread=thread,
        ))
        idx += 1

    await session.commit()

    # Send paginated digest
    for page_items in split_digest_pages(digest_items):
        text = format_digest_page(page_items)
        await message.answer(
            text, parse_mode="HTML", reply_markup=digest_keyboard(page_items),
        )

    if not single_channel:
        user.last_digest_at = datetime.utcnow()
    await session.commit()


@router.callback_query(F.data.startswith("fb:"))
async def handle_feedback(callback: CallbackQuery, session: AsyncSession):
    _, action, rec_id = callback.data.split(":")
    rec = await session.get(Recommendation, int(rec_id))
    if rec:
        rec.feedback = action
        await session.commit()
    await callback.answer("Спасибо за отзыв!")
