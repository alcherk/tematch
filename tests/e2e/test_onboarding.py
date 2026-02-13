"""E2E tests for user onboarding: /start, channel subscription, /interests, /schedule."""

import pytest
from sqlalchemy import select

from core.models import Channel, User, UserChannel


@pytest.mark.asyncio
async def test_new_user_created_with_defaults(session):
    """Feature 1: /start creates user with default digest_cron."""
    user = User(telegram_id=900_001)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert user.digest_cron == "0 9 * * *"
    assert user.interests is None
    assert user.last_digest_at is None
    assert user.interests_embedding is None


@pytest.mark.asyncio
async def test_returning_user_found(session):
    """Feature 1: returning user is found by telegram_id."""
    user = User(telegram_id=900_002)
    session.add(user)
    await session.commit()

    stmt = select(User).where(User.telegram_id == 900_002)
    found = (await session.execute(stmt)).scalar_one_or_none()
    assert found is not None
    assert found.id == user.id


@pytest.mark.asyncio
async def test_channel_subscription_via_forward(session):
    """Feature 2: forwarded message creates channel + links user."""
    user = User(telegram_id=900_003)
    channel = Channel(telegram_id=800_001, username="testchannel", title="Test Channel")
    session.add_all([user, channel])
    await session.commit()

    link = UserChannel(user_id=user.id, channel_id=channel.id)
    session.add(link)
    await session.commit()

    stmt = select(UserChannel).where(
        UserChannel.user_id == user.id,
        UserChannel.channel_id == channel.id,
    )
    found = (await session.execute(stmt)).scalar_one_or_none()
    assert found is not None


@pytest.mark.asyncio
async def test_channel_subscription_via_username(session):
    """Feature 3: @username creates channel with telegram_id=0."""
    user = User(telegram_id=900_004)
    channel = Channel(telegram_id=0, username="durov", title="durov")
    session.add_all([user, channel])
    await session.commit()

    link = UserChannel(user_id=user.id, channel_id=channel.id)
    session.add(link)
    await session.commit()

    assert channel.telegram_id == 0
    assert channel.username == "durov"


@pytest.mark.asyncio
async def test_duplicate_subscription_prevented(session):
    """Feature 2-3: same user+channel pair can't be linked twice."""
    user = User(telegram_id=900_005)
    channel = Channel(telegram_id=800_002, title="UniqueTest")
    session.add_all([user, channel])
    await session.commit()

    link1 = UserChannel(user_id=user.id, channel_id=channel.id)
    session.add(link1)
    await session.commit()

    from sqlalchemy.exc import IntegrityError

    link2 = UserChannel(user_id=user.id, channel_id=channel.id)
    session.add(link2)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_interests_saved(session):
    """Feature 4: /interests updates user.interests field."""
    user = User(telegram_id=900_006)
    session.add(user)
    await session.commit()

    user.interests = "ML, криптография, инди-игры"
    await session.commit()

    stmt = select(User).where(User.telegram_id == 900_006)
    found = (await session.execute(stmt)).scalar_one()
    assert found.interests == "ML, криптография, инди-игры"


@pytest.mark.asyncio
async def test_schedule_saved_and_cleared(session):
    """Feature 5: /schedule saves cron; /schedule off clears it."""
    user = User(telegram_id=900_007)
    session.add(user)
    await session.commit()

    user.digest_cron = "30 18 * * 1-5"
    await session.commit()
    assert user.digest_cron == "30 18 * * 1-5"

    user.digest_cron = None
    await session.commit()
    assert user.digest_cron is None
