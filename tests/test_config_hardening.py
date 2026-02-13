from core.config import Settings


def test_hardening_settings_defaults():
    settings = Settings(
        TG_API_ID=123,
        TG_API_HASH="abc",
        TG_BOT_TOKEN="token",
        DATABASE_URL="postgresql+asyncpg://localhost/test",
    )
    assert settings.DIGEST_WINDOW_MAX_HOURS == 72
    assert settings.MAX_DIGESTS_PER_DAY == 3
    assert settings.DAILY_TOKEN_BUDGET == 500_000
    assert settings.EMBEDDING_BATCH_SIZE == 20
    assert settings.EMBEDDING_FLUSH_INTERVAL == 30
    assert settings.RESYNC_MAX_HOURS == 72
    assert settings.RESYNC_BATCH_SIZE == 100
