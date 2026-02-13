from datetime import datetime, timedelta

from collector.resync import compute_resync_offset


def test_resync_offset_from_last_fetched():
    now = datetime(2026, 2, 13, 12, 0, 0)
    last = datetime(2026, 2, 13, 6, 0, 0)
    offset = compute_resync_offset(last_fetched_at=last, max_hours=72, now=now)
    assert offset == last


def test_resync_offset_none_uses_max():
    now = datetime(2026, 2, 13, 12, 0, 0)
    offset = compute_resync_offset(last_fetched_at=None, max_hours=72, now=now)
    assert offset == now - timedelta(hours=72)


def test_resync_offset_capped():
    now = datetime(2026, 2, 13, 12, 0, 0)
    last = datetime(2026, 1, 1, 0, 0, 0)  # very old
    offset = compute_resync_offset(last_fetched_at=last, max_hours=72, now=now)
    assert offset == now - timedelta(hours=72)
