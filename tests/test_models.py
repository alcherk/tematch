# tests/test_models.py

from core.models import Channel, LLMUsage, Message, Recommendation, User


def test_user_model_has_fields():
    u = User(telegram_id=123, interests="ML and crypto")
    assert u.telegram_id == 123
    assert u.interests == "ML and crypto"
    assert u.digest_cron == "0 9 * * *"


def test_channel_model_has_fields():
    c = Channel(telegram_id=456, username="test_channel", title="Test")
    assert c.telegram_id == 456
    assert c.username == "test_channel"


def test_message_model_has_fields():
    m = Message(channel_id=1, telegram_msg_id=100, text="Hello world")
    assert m.text == "Hello world"
    assert m.embedding is None


def test_recommendation_model_has_fields():
    r = Recommendation(user_id=1, message_id=1, score=0.95)
    assert r.score == 0.95
    assert r.delivered is False
    assert r.feedback is None


def test_message_has_content_hash():
    m = Message(channel_id=1, telegram_msg_id=100, text="Hello world", content_hash="abc123")
    assert m.content_hash == "abc123"


def test_user_has_last_digest_at():
    u = User(telegram_id=123)
    assert u.last_digest_at is None


def test_user_has_interests_embedding():
    u = User(telegram_id=123)
    assert u.interests_embedding is None


def test_llm_usage_model():
    from datetime import date

    usage = LLMUsage(
        date=date.today(),
        provider="openai",
        operation="rank_messages",
        tokens_in=500,
        tokens_out=100,
        cost_estimate=0.001,
    )
    assert usage.provider == "openai"
    assert usage.tokens_in == 500
