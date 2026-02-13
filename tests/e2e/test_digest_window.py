"""E2E tests for hybrid digest window (since-last + max 72h cap)."""

from datetime import datetime, timedelta

from core.recommender import compute_window_start


def test_first_time_user_gets_24h_window():
    """Feature 9: user with no last_digest_at sees last 24 hours."""
    now = datetime(2026, 2, 13, 12, 0)
    start = compute_window_start(last_digest_at=None, max_hours=72, now=now)
    assert start == now - timedelta(hours=24)


def test_recent_digest_window_from_last_digest():
    """Feature 9: window starts from last_digest_at when recent."""
    now = datetime(2026, 2, 13, 12, 0)
    last = datetime(2026, 2, 13, 3, 0)  # 9 hours ago
    start = compute_window_start(last_digest_at=last, max_hours=72, now=now)
    assert start == last


def test_old_digest_capped_at_max_hours():
    """Feature 9: window never goes back more than max_hours."""
    now = datetime(2026, 2, 13, 12, 0)
    last = datetime(2026, 2, 1, 12, 0)  # 12 days ago
    start = compute_window_start(last_digest_at=last, max_hours=72, now=now)
    assert start == now - timedelta(hours=72)
    assert start > last


def test_custom_max_hours():
    """Feature 9: max_hours is configurable (e.g. 24h for tighter window)."""
    now = datetime(2026, 2, 13, 12, 0)
    last = datetime(2026, 2, 11, 0, 0)  # 2.5 days ago
    start = compute_window_start(last_digest_at=last, max_hours=24, now=now)
    assert start == now - timedelta(hours=24)
