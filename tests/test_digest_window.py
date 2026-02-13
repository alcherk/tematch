from datetime import datetime, timedelta

from core.recommender import compute_window_start


def test_window_start_first_time_user():
    now = datetime(2026, 2, 13, 12, 0, 0)
    start = compute_window_start(last_digest_at=None, max_hours=72, now=now)
    assert start == now - timedelta(hours=24)


def test_window_start_recent_digest():
    now = datetime(2026, 2, 13, 12, 0, 0)
    last = datetime(2026, 2, 13, 3, 0, 0)  # 9 hours ago
    start = compute_window_start(last_digest_at=last, max_hours=72, now=now)
    assert start == last


def test_window_start_old_digest_capped_at_max():
    now = datetime(2026, 2, 13, 12, 0, 0)
    last = datetime(2026, 2, 1, 12, 0, 0)  # 12 days ago
    start = compute_window_start(last_digest_at=last, max_hours=72, now=now)
    assert start == now - timedelta(hours=72)
