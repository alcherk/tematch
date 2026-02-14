# tests/test_config.py
import pytest
from pydantic import ValidationError

from core.config import Settings


def test_settings_loads_defaults():
    settings = Settings(
        TG_API_ID=123,
        TG_API_HASH="abc",
        TG_BOT_TOKEN="token",
        DATABASE_URL="postgresql+asyncpg://localhost/test",
    )
    assert settings.LLM_PROVIDER == "openai"
    assert settings.EMBEDDING_DIM == 1536
    assert settings.CANDIDATES_LIMIT == 50
    assert settings.DIGEST_SIZE == 5
    assert settings.DEFAULT_DIGEST_CRON == "0 9 * * *"


def test_settings_requires_telegram_fields(monkeypatch):
    monkeypatch.delenv("TG_API_ID", raising=False)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql+asyncpg://localhost/test", _env_file=None)
