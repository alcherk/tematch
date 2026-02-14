"""Admin API endpoints: stats, costs, health, users."""

import datetime as dt
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_usage import get_daily_token_total
from core.models import Channel, LLMUsage, Message, Recommendation, User, UserChannel
from web.deps import get_session, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _parse_period(period: str) -> dt.date:
    """Convert a period string like '7d' to a start date."""
    days = {"7d": 7, "30d": 30, "90d": 90}
    return dt.date.today() - timedelta(days=days.get(period, 7))


@router.get("/stats")
async def admin_stats(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    """Dashboard summary: user/channel counts, today's activity, costs."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    users = (await session.execute(select(func.count(User.id)))).scalar_one()
    channels = (await session.execute(select(func.count(Channel.id)))).scalar_one()
    messages_today = (
        await session.execute(
            select(func.count(Message.id)).where(Message.created_at >= today_start)
        )
    ).scalar_one()
    recs_today = (
        await session.execute(
            select(func.count(Recommendation.id)).where(
                Recommendation.created_at >= today_start,
                Recommendation.delivered.is_(True),
            )
        )
    ).scalar_one()

    cost_today_row = (
        await session.execute(
            select(func.sum(LLMUsage.cost_estimate)).where(
                LLMUsage.date == dt.date.today()
            )
        )
    ).scalar_one_or_none()

    daily_tokens = await get_daily_token_total(session)

    return {
        "users": users,
        "channels": channels,
        "messages_today": messages_today,
        "recommendations_today": recs_today,
        "cost_today": round(cost_today_row or 0, 4),
        "tokens_today": daily_tokens,
    }


@router.get("/costs")
async def admin_costs(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
    period: str = Query("7d"),
):
    """Per-day, per-provider cost breakdown for the given period."""
    since = _parse_period(period)
    stmt = (
        select(
            LLMUsage.date,
            LLMUsage.provider,
            func.sum(LLMUsage.tokens_in).label("tokens_in"),
            func.sum(LLMUsage.tokens_out).label("tokens_out"),
            func.sum(LLMUsage.cost_estimate).label("cost"),
        )
        .where(LLMUsage.date >= since)
        .group_by(LLMUsage.date, LLMUsage.provider)
        .order_by(LLMUsage.date)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "date": str(r.date),
            "provider": r.provider,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "cost": round(r.cost, 4),
        }
        for r in rows
    ]


@router.get("/health")
async def admin_health(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    """System health: channel freshness, embedding coverage, token budget."""
    from web.main import _settings

    channels_stmt = select(
        Channel.id,
        Channel.title,
        Channel.username,
        Channel.active,
        Channel.last_fetched_at,
    )
    channels = (await session.execute(channels_stmt)).all()

    total_msgs = (
        await session.execute(select(func.count(Message.id)))
    ).scalar_one()
    embedded_msgs = (
        await session.execute(
            select(func.count(Message.id)).where(Message.embedding.isnot(None))
        )
    ).scalar_one()

    daily_tokens = await get_daily_token_total(session)

    now = datetime.utcnow()
    channel_list = []
    for ch in channels:
        if ch.last_fetched_at:
            age_hours = (now - ch.last_fetched_at).total_seconds() / 3600
            status = "green" if age_hours < 1 else "yellow" if age_hours < 6 else "red"
        else:
            status = "red"
            age_hours = None
        channel_list.append(
            {
                "id": ch.id,
                "title": ch.title or ch.username,
                "active": ch.active,
                "last_fetched_hours_ago": round(age_hours, 1) if age_hours else None,
                "status": status,
            }
        )

    return {
        "channels": channel_list,
        "embedding_coverage": (
            round(embedded_msgs / total_msgs * 100, 1) if total_msgs else 0
        ),
        "token_budget": {
            "used": daily_tokens,
            "limit": _settings.DAILY_TOKEN_BUDGET,
            "percent": round(
                daily_tokens / _settings.DAILY_TOKEN_BUDGET * 100, 1
            ),
        },
    }


@router.get("/users")
async def admin_users(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    """List all users with their channel count and digest activity."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    stmt = select(User)
    users = (await session.execute(stmt)).scalars().all()

    result = []
    for u in users:
        ch_count = (
            await session.execute(
                select(func.count(UserChannel.id)).where(UserChannel.user_id == u.id)
            )
        ).scalar_one()

        recs_today = (
            await session.execute(
                select(func.count(Recommendation.id)).where(
                    Recommendation.user_id == u.id,
                    Recommendation.delivered.is_(True),
                    Recommendation.created_at >= today_start,
                )
            )
        ).scalar_one()

        result.append(
            {
                "telegram_id": u.telegram_id,
                "interests": u.interests[:80] if u.interests else None,
                "digest_cron": u.digest_cron,
                "channels": ch_count,
                "digests_today": recs_today,
                "last_digest_at": (
                    u.last_digest_at.isoformat() if u.last_digest_at else None
                ),
            }
        )
    return result
