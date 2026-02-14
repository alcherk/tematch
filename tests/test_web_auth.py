"""Tests for Telegram Login Widget verification and JWT."""

import hashlib
import hmac
import time

from web.auth import create_jwt, decode_jwt, verify_telegram_login


def _make_telegram_data(bot_token: str) -> dict:
    """Build valid Telegram Login Widget payload with correct hash."""
    data = {
        "id": 123456,
        "first_name": "Test",
        "auth_date": str(int(time.time())),
    }
    # Telegram hash: HMAC-SHA256 with key=SHA256(bot_token)
    secret = hashlib.sha256(bot_token.encode()).digest()
    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data) if k != "hash")
    data["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return data


def test_verify_telegram_login_valid():
    token = "123:ABC"
    data = _make_telegram_data(token)
    result = verify_telegram_login(data, token)
    assert result is True


def test_verify_telegram_login_bad_hash():
    data = {"id": 1, "first_name": "X", "auth_date": "1", "hash": "badhash"}
    result = verify_telegram_login(data, "123:ABC")
    assert result is False


def test_verify_telegram_login_expired():
    token = "123:ABC"
    data = _make_telegram_data(token)
    data["auth_date"] = str(int(time.time()) - 90000)  # >24h ago
    # Recompute hash with old auth_date
    secret = hashlib.sha256(token.encode()).digest()
    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data) if k != "hash")
    data["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    result = verify_telegram_login(data, token)
    assert result is False


def test_jwt_roundtrip():
    secret = "testsecret"
    token = create_jwt(telegram_id=42, secret=secret)
    payload = decode_jwt(token, secret=secret)
    assert payload["telegram_id"] == 42


def test_jwt_expired():
    secret = "testsecret"
    token = create_jwt(telegram_id=42, secret=secret, expires_hours=-1)
    payload = decode_jwt(token, secret=secret)
    assert payload is None
