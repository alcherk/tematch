import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import LLMUsage


async def log_usage(
    session: AsyncSession,
    provider: str,
    operation: str,
    tokens_in: int,
    tokens_out: int,
    cost_estimate: float = 0.0,
) -> None:
    entry = LLMUsage(
        date=dt.date.today(),
        provider=provider,
        operation=operation,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_estimate=cost_estimate,
    )
    session.add(entry)
    await session.commit()


async def get_daily_token_total(session: AsyncSession) -> int:
    stmt = select(func.sum(LLMUsage.tokens_in + LLMUsage.tokens_out)).where(
        LLMUsage.date == dt.date.today()
    )
    result = await session.execute(stmt)
    total = result.scalar_one_or_none()
    return total or 0
