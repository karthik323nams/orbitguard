from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import combinations
from math import floor, sqrt
from typing import Optional, Union

from ..models.orbital import CandidatePair, ConjunctionEvent, OrbitalElements
from .conjunction import find_closest_approach
from .propagation import propagate


@dataclass(frozen=True)
class ScanConfig:
    duration_minutes: int = 90
    coarse_step_seconds: int = 60
    screening_distance_km: float = 10.0
    # Safety buffer used because the coarse screen samples discrete epochs.
    # With a conservative relative-speed bound, it reduces the chance of
    # missing an approach that crosses the threshold between samples.
    max_relative_speed_bound_km_s: float = 20.0
    refinement_window_seconds: int = 60
    max_objects: int = 250
    max_events: int = 50

    @property
    def step_seconds(self) -> int:
        return self.coarse_step_seconds


def _cell(position: tuple[float, float, float], cell_size_km: float) -> tuple[int, int, int]:
    return tuple(floor(value / cell_size_km) for value in position)


def _neighbor_cells(cell: tuple[int, int, int]):
    cx, cy, cz = cell
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                yield (cx + dx, cy + dy, cz + dz)


def _candidate_pairs(
    elements: list[OrbitalElements],
    start: datetime,
    config: ScanConfig,
    satrecs: Optional[dict] = None,
) -> list[CandidatePair]:
    elements = elements[: config.max_objects]
    if len(elements) < 2:
        return []

    pair_keys: set[tuple[int, int]] = set()
    active_indices = set(range(len(elements)))

    # A discrete-time screen can miss an encounter that happens between two
    # samples. Expand the spatial-cell search radius by a conservative bound
    # on how far two objects can close during one interval.
    interval_buffer_km = config.max_relative_speed_bound_km_s * config.coarse_step_seconds
    candidate_distance_km = config.screening_distance_km + interval_buffer_km
    cell_size = max(candidate_distance_km, 1.0)

    for offset in range(0, config.duration_minutes * 60 + 1, config.coarse_step_seconds):
        timestamp = start + timedelta(seconds=offset)
        buckets: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        states = []

        for index, element in enumerate(elements):
            if index not in active_indices:
                continue
            try:
                state = propagate(element, timestamp, satrec=(satrecs or {}).get(element.catalog_number))
            except (TypeError, ValueError, RuntimeError):
                active_indices.discard(index)
                continue
            states.append((index, state))
            buckets[_cell(state.position, cell_size)].append(index)

        for index, state in states:
            own_cell = _cell(state.position, cell_size)
            for cell in _neighbor_cells(own_cell):
                for other_index in buckets.get(cell, []):
                    if other_index <= index or other_index not in active_indices:
                        continue
                    b_state = next((s for i, s in states if i == other_index), None)
                    if b_state is None:
                        continue
                    dx = state.x_km - b_state.x_km
                    dy = state.y_km - b_state.y_km
                    dz = state.z_km - b_state.z_km
                    d = sqrt(dx * dx + dy * dy + dz * dz)
                    if d <= candidate_distance_km:
                        pair_keys.add((index, other_index))

    return [CandidatePair(a=elements[i], b=elements[j]) for i, j in sorted(pair_keys)]


def scan_conjunctions(
    elements: list[OrbitalElements],
    start: Optional[datetime] = None,
    config: Optional[ScanConfig] = None,
    satrecs: Optional[dict] = None,
) -> list[ConjunctionEvent]:
    config = config or ScanConfig()
    start = start or datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    else:
        start = start.astimezone(timezone.utc)

    if len(elements) < 2:
        return []
    if config.max_objects < 2:
        raise ValueError("max_objects must be at least 2")
    if config.screening_distance_km <= 0:
        raise ValueError("screening_distance_km must be positive")
    if config.coarse_step_seconds <= 0:
        raise ValueError("coarse_step_seconds must be positive")
    if config.max_relative_speed_bound_km_s <= 0:
        raise ValueError("max_relative_speed_bound_km_s must be positive")

    candidates = _candidate_pairs(elements, start, config, satrecs=satrecs)
    events: list[ConjunctionEvent] = []
    for candidate in candidates:
        try:
            event = find_closest_approach(
                candidate.a,
                candidate.b,
                start,
                duration_minutes=config.duration_minutes,
                step_seconds=config.coarse_step_seconds,
                refinement_half_window_seconds=config.refinement_window_seconds,
                sat_a=(satrecs or {}).get(candidate.a.catalog_number),
                sat_b=(satrecs or {}).get(candidate.b.catalog_number),
            )
        except (ValueError, RuntimeError):
            continue
        if event.miss_distance_km <= config.screening_distance_km:
            events.append(event)

    events.sort(key=lambda e: (e.miss_distance_km, e.closest_approach))
    return events[: config.max_events]
