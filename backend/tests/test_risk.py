from datetime import datetime, timedelta, timezone

from app.services.risk import assess_risk


def test_risk_is_higher_for_closer_more_imminent_event():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    close = assess_risk(1.0, 12.0, 10.0, now - timedelta(hours=1), now - timedelta(hours=1), now)
    far = assess_risk(50.0, 5.0, 360.0, now - timedelta(hours=1), now - timedelta(hours=1), now)
    assert close.score > far.score
    assert close.band in {"HIGH", "CRITICAL"}


def test_risk_is_bounded():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = assess_risk(0.0, 100.0, 0.0, now, now, now)
    assert 0.0 <= result.score <= 100.0
    assert result.band in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
