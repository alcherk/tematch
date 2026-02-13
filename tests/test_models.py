# tests/test_models.py

from core.models import Channel, Message, Recommendation, User


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
