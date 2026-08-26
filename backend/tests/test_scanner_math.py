from __future__ import annotations

from datetime import datetime, timezone

from app.config import get_tracked_catalog_numbers
from app.models.orbital import OrbitalElements, PropagatedState
from app.services.cache import cache_status_for_group
from app.services.scanner import ScanConfig, _cell


def test_default_tracked_catalogs_include_multiple_real_objects() -> None:
    values = get_tracked_catalog_numbers()
    assert len(values) > 1
    assert 25544 in values
    assert all(value > 0 for value in values)


def test_cell_is_deterministic() -> None:
    assert _cell((100.0, 200.0, 300.0), 50.0) == (2, 4, 6)


def test_screening_config_has_discrete_time_safety_bound() -> None:
    cfg = ScanConfig(coarse_step_seconds=30, screening_distance_km=50.0, max_relative_speed_bound_km_s=20.0)
    buffer_km = cfg.max_relative_speed_bound_km_s * cfg.coarse_step_seconds
    assert buffer_km == 600.0
    assert cfg.screening_distance_km + buffer_km == 650.0


def test_catalog_numbers_are_not_limited_to_five_digits() -> None:
    element = OrbitalElements(
        name="NEW OBJECT",
        catalog_number=100100,
        line1="",
        line2="",
        epoch=datetime.now(timezone.utc),
    )
    assert element.catalog_number == 100100


def test_partial_cache_is_not_marked_fresh_when_more_objects_are_expected() -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = [{
        "catalog_number": 25544,
        "object_name": "ISS (ZARYA)",
        "source_group": "tracked",
        "epoch": now,
        "raw_json": "{}",
        "fetched_at": now,
        "last_successful_fetch": now,
        "cache_fresh": 1,
    }]

    status = cache_status_for_group("tracked", cached_rows=rows, configured_objects=3)

    assert status["object_count"] == 1
    assert status["configured_objects"] == 3
    assert status["cache_fresh"] is False
    assert status["stale"] is True
    assert status["failed_objects"] == 2
