from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class OrbitalElements:
    name: str
    catalog_number: int
    line1: str
    line2: str
    epoch: Optional[datetime] = None


@dataclass(frozen=True)
class PropagatedState:
    timestamp: datetime
    x_km: float
    y_km: float
    z_km: float
    vx_km_s: float
    vy_km_s: float
    vz_km_s: float

    @property
    def position(self) -> tuple[float, float, float]:
        return (self.x_km, self.y_km, self.z_km)

    @property
    def velocity(self) -> tuple[float, float, float]:
        return (self.vx_km_s, self.vy_km_s, self.vz_km_s)


@dataclass(frozen=True)
class ConjunctionEvent:
    object_a_name: str
    object_a_catalog_number: int
    object_b_name: str
    object_b_catalog_number: int
    closest_approach: datetime
    miss_distance_km: float
    relative_speed_km_s: float
    severity: str
    scan_window_minutes: int
    risk_score: float = 0.0
    risk_breakdown: Optional[dict] = None
    id: Optional[str] = None


@dataclass(frozen=True)
class CandidatePair:
    a: OrbitalElements
    b: OrbitalElements
