from __future__ import annotations

from datetime import datetime, timedelta

from .propagation import propagate


def trajectory_window(elements, start: datetime, duration_minutes: int, step_seconds: int, satrec=None):
    """Return propagated positions for an arbitrary UTC time window."""
    if duration_minutes <= 0 or step_seconds <= 0:
        raise ValueError("duration_minutes and step_seconds must be positive")
    count = duration_minutes * 60 // step_seconds
    return [
        propagate(elements, start + timedelta(seconds=i * step_seconds), satrec=satrec)
        for i in range(count + 1)
    ]
