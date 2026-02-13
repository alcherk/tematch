"""E2E tests for collector resync (catch-up on startup)."""

from datetime import datetime, timedelta

from collector.resync import compute_resync_offset


def test_resync_from_last_fetched():
    """Feature 13: resync starts from channel.last_fetched_at."""
    now = datetime(2026, 2, 13, 12, 0)
    last = datetime(2026, 2, 13, 6, 0)  # 6 hours ago
    offset = compute_resync_offset(last_fetched_at=last, max_hours=72, now=now)
    assert offset == last


def test_resync_none_uses_max_hours():
    """Feature 13: no last_fetched_at falls back to max_hours ago."""
    now = datetime(2026, 2, 13, 12, 0)
    offset = compute_resync_offset(last_fetched_at=None, max_hours=72, now=now)
    assert offset == now - timedelta(hours=72)


def test_resync_capped_at_max_hours():
    """Feature 13: very old last_fetched_at is capped at max_hours."""
    now = datetime(2026, 2, 13, 12, 0)
    old = datetime(2026, 1, 1, 0, 0)  # 43 days ago
    offset = compute_resync_offset(last_fetched_at=old, max_hours=72, now=now)
    assert offset == now - timedelta(hours=72)
    assert offset > old


def test_resync_custom_max_hours():
    """Feature 13: RESYNC_MAX_HOURS is configurable."""
    now = datetime(2026, 2, 13, 12, 0)
    offset = compute_resync_offset(last_fetched_at=None, max_hours=24, now=now)
    assert offset == now - timedelta(hours=24)
