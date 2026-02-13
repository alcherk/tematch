from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Channel


async def get_active_channel_ids(session: AsyncSession) -> list[int]:
    stmt = select(Channel.telegram_id).where(Channel.active.is_(True))
    result = await session.execute(stmt)
    return result.scalars().all()
