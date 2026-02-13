"""E2E tests for rate limiting (digest cap + token budget)."""

import datetime as dt
from datetime import datetime

import pytest
from sqlalchemy import select

from core.llm_usage import get_daily_token_total, log_usage
from core.models import Channel, LLMUsage, Message, Recommendation, User


@pytest.mark.asyncio
async def test_digest_count_with_delivered_recommendations(session):
    """Feature 7: delivered recommendations are counted as digests."""
    user = User(telegram_id=600_001, interests="ML")
    ch = Channel(telegram_id=500_001, title="TestCh")
    session.add_all([user, ch])
    await session.commit()

    msg = Message(
        channel_id=ch.id, telegram_msg_id=1,
        text="Test message for rate limit test content",
        date=datetime.utcnow(),
    )
    session.add(msg)
    await session.commit()

    # Create 3 delivered recommendations (= 1 digest batch within same minute)
    for i in range(3):
        rec = Recommendation(
            user_id=user.id, message_id=msg.id,
            score=0.9 - i * 0.1, delivered=True,
        )
        session.add(rec)
    await session.commit()

    from bot.handlers.digest import count_digests_today

    count = await count_digests_today(session, user.id)
    assert count >= 1


@pytest.mark.asyncio
async def test_token_budget_tracking(session):
    """Feature 8+16: LLM usage logged and summed correctly."""
    usage = LLMUsage(
        date=dt.date.today(), provider="openai",
        operation="rank_messages", tokens_in=300_000,
        tokens_out=50_000, cost_estimate=0.35,
    )
    session.add(usage)
    await session.commit()

    total = await get_daily_token_total(session)
    assert total >= 350_000


@pytest.mark.asyncio
async def test_token_budget_sums_multiple_entries(session):
    """Feature 8: multiple usage entries are summed for the day."""
    for i in range(3):
        usage = LLMUsage(
            date=dt.date.today(), provider="openai",
            operation=f"op_{i}", tokens_in=10_000,
            tokens_out=5_000,
        )
        session.add(usage)
    await session.commit()

    total = await get_daily_token_total(session)
    assert total >= 45_000  # 3 * (10k + 5k)


@pytest.mark.asyncio
async def test_log_usage_creates_row(session):
    """Feature 16: log_usage writes a row to llm_usage table."""
    await log_usage(
        session=session, provider="claude",
        operation="rank_messages",
        tokens_in=1_000, tokens_out=200,
        cost_estimate=0.01,
    )

    stmt = select(LLMUsage).where(LLMUsage.provider == "claude")
    found = (await session.execute(stmt)).scalars().all()
    assert len(found) >= 1
    assert found[-1].tokens_in == 1_000
    assert found[-1].tokens_out == 200
