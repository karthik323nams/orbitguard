from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.optimize import minimize_scalar

from ..models.orbital import ConjunctionEvent, OrbitalElements
from .propagation import propagate
from .risk import assess_risk


def _distance_km(a, b) -> float:
    return math.sqrt((a.x_km - b.x_km) ** 2 + (a.y_km - b.y_km) ** 2 + (a.z_km - b.z_km) ** 2)


def _relative_speed_km_s(a, b) -> float:
    return math.sqrt((a.vx_km_s - b.vx_km_s) ** 2 + (a.vy_km_s - b.vy_km_s) ** 2 + (a.vz_km_s - b.vz_km_s) ** 2)


def find_closest_approach(
    elements_a: OrbitalElements,
    elements_b: OrbitalElements,
    start: datetime,
    duration_minutes: int = 120,
    step_seconds: int = 30,
    refinement_half_window_seconds: int = 45,
    sat_a=None,
    sat_b=None,
) -> ConjunctionEvent:
    if elements_a.catalog_number == elements_b.catalog_number:
        raise ValueError("A conjunction pair must contain two different objects.")
    if duration_minutes <= 0 or step_seconds <= 0:
        raise ValueError("duration_minutes and step_seconds must be positive")

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    else:
        start = start.astimezone(timezone.utc)

    n_steps = duration_minutes * 60 // step_seconds
    best_index = 0
    best_distance = float("inf")
    states_a = []
    states_b = []

    for i in range(n_steps + 1):
        timestamp = start + timedelta(seconds=i * step_seconds)
        state_a = propagate(elements_a, timestamp, satrec=sat_a)
        state_b = propagate(elements_b, timestamp, satrec=sat_b)
        states_a.append(state_a)
        states_b.append(state_b)
        d = _distance_km(state_a, state_b)
        if d < best_distance:
            best_distance = d
            best_index = i

    coarse_time = start + timedelta(seconds=best_index * step_seconds)
    left = max(start, coarse_time - timedelta(seconds=refinement_half_window_seconds))
    right = min(start + timedelta(minutes=duration_minutes), coarse_time + timedelta(seconds=refinement_half_window_seconds))

    def objective(seconds_from_start: float) -> float:
        t = start + timedelta(seconds=float(seconds_from_start))
        return _distance_km(propagate(elements_a, t, satrec=sat_a), propagate(elements_b, t, satrec=sat_b))

    res = minimize_scalar(
        objective,
        bounds=((left - start).total_seconds(), (right - start).total_seconds()),
        method="bounded",
        options={"xatol": 0.25, "maxiter": 80},
    )
    tca = start + timedelta(seconds=float(res.x))
    state_a = propagate(elements_a, tca, satrec=sat_a)
    state_b = propagate(elements_b, tca, satrec=sat_b)
    miss_distance = _distance_km(state_a, state_b)
    rel_speed = _relative_speed_km_s(state_a, state_b)
    time_to_tca_minutes = max(0.0, (tca - start).total_seconds() / 60.0)
    assessment = assess_risk(
        miss_distance_km=miss_distance,
        relative_speed_km_s=rel_speed,
        time_to_tca_minutes=time_to_tca_minutes,
        epoch_a=elements_a.epoch,
        epoch_b=elements_b.epoch,
        now=start,
    )

    return ConjunctionEvent(
        object_a_name=elements_a.name,
        object_a_catalog_number=elements_a.catalog_number,
        object_b_name=elements_b.name,
        object_b_catalog_number=elements_b.catalog_number,
        closest_approach=tca,
        miss_distance_km=miss_distance,
        relative_speed_km_s=rel_speed,
        severity=assessment.band,
        scan_window_minutes=duration_minutes,
        risk_score=assessment.score,
        risk_breakdown={
            "miss_distance_score": assessment.miss_distance_score,
            "imminence_score": assessment.imminence_score,
            "relative_speed_score": assessment.relative_speed_score,
            "freshness_score": assessment.freshness_score,
            "time_to_tca_minutes": round(time_to_tca_minutes, 1),
            "uncertainty_status": assessment.uncertainty_status,
            "reasons": list(assessment.reasons),
        },
    )
