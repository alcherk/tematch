from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional

import jwt


def verify_telegram_login(
    data: dict, bot_token: str, max_age: int = 86400
) -> bool:
    """Verify Telegram Login Widget data using HMAC-SHA256."""
    check_hash = data.get("hash", "")
    auth_date = int(data.get("auth_date", 0))

    if time.time() - auth_date > max_age:
        return False

    secret = hashlib.sha256(bot_token.encode()).digest()
    check_string = "\n".join(
        f"{k}={data[k]}" for k in sorted(data) if k != "hash"
    )
    computed = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, check_hash)


def create_jwt(
    telegram_id: int, secret: str, expires_hours: int = 24
) -> str:
    """Create a JWT token with telegram_id claim."""
    payload = {
        "telegram_id": telegram_id,
        "exp": datetime.utcnow() + timedelta(hours=expires_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_jwt(token: str, secret: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns None if expired or invalid."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
