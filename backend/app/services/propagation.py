from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sgp4.api import Satrec

from ..models.orbital import OrbitalElements, PropagatedState

# WGS-84 / SGP4 constants
_GM_KM3_S2 = 3.986004418e5   # gravitational parameter km³/s²
_RE_KM = 6378.137             # Earth equatorial radius km


# ---------------------------------------------------------------------------
# Orbital parameter helpers
# ---------------------------------------------------------------------------

def orbital_period_minutes(mean_motion_rev_day: float) -> float:
    """Return the orbital period in minutes from mean motion in rev/day."""
    if mean_motion_rev_day <= 0:
        return 90.0  # safe fallback
    return 1440.0 / mean_motion_rev_day   # 1440 min/day


def semi_major_axis_km(mean_motion_rev_day: float) -> float:
    """Return semi-major axis in km from mean motion in rev/day."""
    if mean_motion_rev_day <= 0:
        return _RE_KM + 400.0  # fallback ~LEO
    n_rad_s = mean_motion_rev_day * 2.0 * math.pi / 86400.0
    return (_GM_KM3_S2 / (n_rad_s ** 2)) ** (1.0 / 3.0)


def apogee_perigee_km(mean_motion_rev_day: float, eccentricity: float) -> tuple[float, float]:
    """Return (apogee_km, perigee_km) altitudes above Earth's surface."""
    a = semi_major_axis_km(mean_motion_rev_day)
    apogee = a * (1.0 + eccentricity) - _RE_KM
    perigee = a * (1.0 - eccentricity) - _RE_KM
    return round(float(apogee), 2), round(float(perigee), 2)


def classify_orbit_regime(
    mean_motion_rev_day: float,
    eccentricity: float,
    inclination_deg: float,
) -> str:
    """Classify the orbit regime based on orbital parameters."""
    a = semi_major_axis_km(mean_motion_rev_day)
    mean_alt_km = a - _RE_KM

    if eccentricity > 0.25:
        return "HEO"
    if mean_alt_km < 2000.0:
        # Check for sun-synchronous (SSO): inclination ~96–98°, LEO
        if 96.0 <= inclination_deg <= 99.0 and mean_alt_km < 1000.0:
            return "SSO"
        return "LEO"
    if mean_alt_km < 35000.0:
        return "MEO"
    # GEO band: ~35786 km, low eccentricity, near-equatorial
    if mean_alt_km < 42000.0 and eccentricity < 0.01 and inclination_deg < 10.0:
        return "GEO"
    return "GEO+"


def _ensure_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _satrec(elements: OrbitalElements) -> Satrec:
    return Satrec.twoline2rv(elements.line1, elements.line2)


def _coerce_elements(candidate: Any) -> OrbitalElements:
    if isinstance(candidate, OrbitalElements):
        return candidate
    if isinstance(candidate, dict):
        line1 = str(candidate.get("line1") or "")
        line2 = str(candidate.get("line2") or "")
        if not line1 or not line2:
            raise ValueError("Orbit object requires both line1 and line2")
        return OrbitalElements(
            name=str(candidate.get("name") or candidate.get("object_name") or f"CATALOG {candidate.get('catalog_number', 0)}"),
            catalog_number=int(candidate.get("catalog_number") or candidate.get("norad_id") or 0),
            line1=line1,
            line2=line2,
            epoch=candidate.get("epoch"),
        )
    raise TypeError(f"Unsupported orbit object type: {type(candidate)!r}")


def propagate(elements: OrbitalElements, timestamp: datetime, satrec=None) -> PropagatedState:
    timestamp = _ensure_utc(timestamp)
    sat = satrec if satrec is not None else _satrec(_coerce_elements(elements))
    jd = timestamp.toordinal() + 1721424.5
    seconds = (timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second + timestamp.microsecond / 1e6)
    jd += seconds / 86400.0
    jd1 = int(jd)
    jd2 = jd - jd1
    error, position, velocity = sat.sgp4(jd1, jd2)
    if error != 0:
        raise RuntimeError(f"SGP4 propagation failed for {sat.satnum}; error code {error}")
    return PropagatedState(
        timestamp=timestamp,
        x_km=float(position[0]), y_km=float(position[1]), z_km=float(position[2]),
        vx_km_s=float(velocity[0]), vy_km_s=float(velocity[1]), vz_km_s=float(velocity[2]),
    )


def propagate_forward(elements: OrbitalElements, start: datetime, duration_minutes: int, step_seconds: int, satrec=None) -> list[PropagatedState]:
    if duration_minutes <= 0 or step_seconds <= 0:
        raise ValueError("duration_minutes and step_seconds must be positive")
    start = _ensure_utc(start)
    total_seconds = duration_minutes * 60
    return [
        propagate(_coerce_elements(elements), start + timedelta(seconds=offset), satrec=satrec)
        for offset in range(0, total_seconds + 1, step_seconds)
    ]


def propagate_object(object_or_row: Any, *, start: Optional[datetime] = None, duration_minutes: int = 60, step_seconds: int = 60, satrec=None) -> list[PropagatedState]:
    elements = _coerce_elements(object_or_row)
    start_dt = _ensure_utc(start or datetime.now(timezone.utc))
    return propagate_forward(elements, start_dt, duration_minutes=duration_minutes, step_seconds=step_seconds, satrec=satrec)
