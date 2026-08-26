from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Optional


@dataclass(frozen=True)
class RiskAssessment:
    score: float
    band: str
    miss_distance_score: float
    imminence_score: float
    relative_speed_score: float
    freshness_score: float
    uncertainty_status: str
    reasons: tuple[str, ...]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _linear_decay(value: float, good: float, bad: float) -> float:
    if value <= good:
        return 1.0
    if value >= bad:
        return 0.0
    return 1.0 - (value - good) / (bad - good)


def _freshness_hours(epoch: Optional[datetime], now: Optional[datetime] = None) -> Optional[float]:
    if epoch is None:
        return None
    now = now or datetime.now(timezone.utc)
    if epoch.tzinfo is None:
        epoch = epoch.replace(tzinfo=timezone.utc)
    return max(0.0, (now - epoch.astimezone(timezone.utc)).total_seconds() / 3600.0)


def _band(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def assess_risk(
    miss_distance_km: float,
    relative_speed_km_s: float,
    time_to_tca_minutes: float,
    epoch_a: Optional[datetime] = None,
    epoch_b: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> RiskAssessment:
    """Transparent prototype prioritization index, not operational Pc.

    We deliberately do not fabricate covariance or collision probability because
    public GP/OMM records used by the MVP do not provide the covariance inputs
    required by operational probability-of-collision calculations.
    """
    miss = 100.0 * math.exp(-max(miss_distance_km, 0.0) / 8.0)
    imminence = 100.0 * math.exp(-max(time_to_tca_minutes, 0.0) / 180.0)
    rel_speed = 100.0 * _clamp01(relative_speed_km_s / 15.0)

    ages = [a for a in (_freshness_hours(epoch_a, now), _freshness_hours(epoch_b, now)) if a is not None]
    if ages:
        freshness = 100.0 * _linear_decay(max(ages), 3.0, 48.0)
        freshness_hours = max(ages)
    else:
        freshness = 50.0
        freshness_hours = None

    score = 0.55 * miss + 0.20 * imminence + 0.15 * rel_speed + 0.10 * freshness
    score = round(max(0.0, min(100.0, score)), 1)
    band = _band(score)

    reasons: list[str] = []
    if miss_distance_km < 5:
        reasons.append(f"very small miss distance ({miss_distance_km:.2f} km)")
    elif miss_distance_km < 25:
        reasons.append(f"close predicted approach ({miss_distance_km:.2f} km)")
    if time_to_tca_minutes <= 30:
        reasons.append(f"TCA is imminent ({time_to_tca_minutes:.0f} min)")
    elif time_to_tca_minutes <= 180:
        reasons.append(f"TCA is within {time_to_tca_minutes:.0f} min")
    if relative_speed_km_s >= 10:
        reasons.append(f"high relative speed ({relative_speed_km_s:.1f} km/s)")
    if freshness_hours is not None and freshness_hours > 24:
        reasons.append(f"stale orbital epoch ({freshness_hours:.0f} h old)")
    if not reasons:
        reasons.append("screened as a lower-priority proximity event")

    return RiskAssessment(
        score=score,
        band=band,
        miss_distance_score=round(miss, 1),
        imminence_score=round(imminence, 1),
        relative_speed_score=round(rel_speed, 1),
        freshness_score=round(freshness, 1),
        uncertainty_status="NOT AVAILABLE: covariance required for operational Pc",
        reasons=tuple(reasons),
    )


def risk_band(miss_distance_km: float) -> str:
    """Backward-compatible helper for callers that only have miss distance."""
    if miss_distance_km < 1.0:
        return "CRITICAL"
    if miss_distance_km < 5.0:
        return "HIGH"
    if miss_distance_km < 25.0:
        return "MEDIUM"
    return "LOW"
