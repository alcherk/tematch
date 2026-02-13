from core.content_hash import compute_content_hash
from core.recommender import deduplicate_candidates


def test_compute_content_hash_basic():
    h = compute_content_hash("Hello World")
    assert len(h) == 64  # SHA-256 hex


def test_compute_content_hash_normalizes_whitespace():
    h1 = compute_content_hash("hello   world")
    h2 = compute_content_hash("hello world")
    assert h1 == h2


def test_compute_content_hash_case_insensitive():
    h1 = compute_content_hash("Hello World")
    h2 = compute_content_hash("hello world")
    assert h1 == h2


def test_compute_content_hash_strips():
    h1 = compute_content_hash("  hello world  ")
    h2 = compute_content_hash("hello world")
    assert h1 == h2



def test_deduplicate_keeps_earliest():
    from datetime import datetime
    from unittest.mock import MagicMock

    msg1 = MagicMock(id=1, text="Hello", content_hash="aaa", date=datetime(2026, 1, 1, 10, 0))
    msg2 = MagicMock(id=2, text="Hello", content_hash="aaa", date=datetime(2026, 1, 1, 12, 0))
    msg3 = MagicMock(id=3, text="Other", content_hash="bbb", date=datetime(2026, 1, 1, 11, 0))

    result = deduplicate_candidates([msg1, msg2, msg3])
    assert len(result) == 2
    ids = [m.id for m in result]
    assert 1 in ids  # earliest of hash "aaa"
    assert 3 in ids
    assert 2 not in ids
