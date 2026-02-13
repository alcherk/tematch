from scheduler.jobs import parse_cron


def test_parse_cron_valid():
    result = parse_cron("0 9 * * *")
    assert result == {
        "minute": "0",
        "hour": "9",
        "day": "*",
        "month": "*",
        "day_of_week": "*",
    }


def test_parse_cron_invalid_returns_none():
    result = parse_cron("invalid")
    assert result is None


def test_parse_cron_none_returns_none():
    result = parse_cron(None)
    assert result is None
