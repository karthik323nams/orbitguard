from __future__ import annotations
from datetime import datetime, timezone
import math

EARTH_EQUATORIAL_RADIUS_KM = 6378.137
EARTH_FLATTENING = 1.0 / 298.257223563
EARTH_E2 = EARTH_FLATTENING * (2.0 - EARTH_FLATTENING)

def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def julian_date(dt: datetime) -> float:
    dt = _utc(dt)
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + (dt.minute + (dt.second + dt.microsecond / 1e6) / 60.0) / 60.0) / 24.0
    if m <= 2:
        y -= 1; m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5

def gmst_radians(dt: datetime) -> float:
    jd = julian_date(dt)
    t = (jd - 2451545.0) / 36525.0
    deg = (280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933*t*t - t*t*t/38710000.0) % 360.0
    return math.radians(deg)

def teme_to_ecef(x_km: float, y_km: float, z_km: float, timestamp: datetime) -> tuple[float,float,float]:
    theta = gmst_radians(timestamp)
    c, s = math.cos(theta), math.sin(theta)
    return c*x_km + s*y_km, -s*x_km + c*y_km, z_km

def ecef_to_geodetic(x_km: float, y_km: float, z_km: float) -> tuple[float,float,float]:
    lon = math.degrees(math.atan2(y_km, x_km))
    p = math.hypot(x_km, y_km)
    lat = math.atan2(z_km, p * (1.0 - EARTH_E2))
    for _ in range(8):
        sin_lat = math.sin(lat)
        n = EARTH_EQUATORIAL_RADIUS_KM / math.sqrt(1.0 - EARTH_E2*sin_lat*sin_lat)
        alt = p / max(math.cos(lat), 1e-12) - n
        lat = math.atan2(z_km, p * (1.0 - EARTH_E2*n/max(n+alt, 1e-12)))
    sin_lat = math.sin(lat)
    n = EARTH_EQUATORIAL_RADIUS_KM / math.sqrt(1.0 - EARTH_E2*sin_lat*sin_lat)
    alt = p / max(math.cos(lat), 1e-12) - n
    return math.degrees(lat), lon, alt
