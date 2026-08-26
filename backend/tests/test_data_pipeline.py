from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
import requests

from app.database.db import connect, init_db, upsert_elements
from app.models.orbital import OrbitalElements
from app.main import _satrec_from_omm_payload, get_object_trajectory
from app.services.cache import (
    cache_status_for_group,
    list_cached_objects,
    refresh_group_from_omm,
    resolve_catalogs_from_cache,
)
from app.services.celestrak import CelesTrakError, get_tracked_catalog_numbers, validate_omm_record
from app.services.conjunction import find_closest_approach
from app.services.propagation import propagate_object
from app.services.scanner import ScanConfig, _candidate_pairs, scan_conjunctions


def reset_cache():
    with connect() as conn:
        if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orbital_elements'").fetchone():
            conn.execute("DELETE FROM orbital_elements")


def test_tracked_catalogs_default_to_multi_object_set(monkeypatch):
    monkeypatch.delenv("ORBITGUARD_TRACKED_CATALOGS", raising=False)
    values = get_tracked_catalog_numbers()
    assert len(values) > 1
    assert 25544 in values
    assert all(value > 0 for value in values)


def test_tracked_catalogs_trim_dedupe_and_reject_invalid(monkeypatch):
    monkeypatch.setenv("ORBITGUARD_TRACKED_CATALOGS", " 25544, 25544 , 12345 ,  abc ")
    with pytest.raises(ValueError):
        get_tracked_catalog_numbers()

    monkeypatch.setenv("ORBITGUARD_TRACKED_CATALOGS", " 25544, 25544 , 12345 ")
    assert get_tracked_catalog_numbers() == [25544, 12345]


def test_valid_omm_record_is_accepted():
    sample = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "EPOCH": "2026-08-21T04:00:00Z",
        "MEAN_MOTION": 15.499,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 0.0000001,
    }
    validated = validate_omm_record(sample)
    assert validated["NORAD_CAT_ID"] == 25544
    assert validated["OBJECT_NAME"] == "ISS (ZARYA)"


def test_invalid_omm_record_is_rejected():
    with pytest.raises(ValueError):
        validate_omm_record({"OBJECT_NAME": "bad"})


def test_cache_write_and_read_round_trip():
    reset_cache()
    init_db()
    element = OrbitalElements(
        name="ISS (ZARYA)",
        catalog_number=25544,
        line1="1 25544U 98067A   26234.00000000  .00000000  00000-0  00000-0 0  9991",
        line2="2 25544  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
        epoch=datetime.now(timezone.utc),
    )
    fields = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "MEAN_MOTION": 15.5,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 0.0000001,
    }

    refresh_group_from_omm([(element, None, fields)], group="tracked")
    rows = resolve_catalogs_from_cache([25544], group="tracked")
    assert len(rows) == 1
    assert rows[0][0].catalog_number == 25544


def test_cache_status_marks_stale_records():
    stale_epoch = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    status = cache_status_for_group("tracked", cached_rows=[{"catalog_number": 25544, "fetched_at": stale_epoch, "last_successful_fetch": stale_epoch}])
    assert status["cache_fresh"] is False
    assert status["mode"] in {"CACHED", "LIVE"}


def test_403_uses_cached_data_when_available():
    reset_cache()
    init_db()
    element = OrbitalElements(
        name="ISS (ZARYA)",
        catalog_number=25544,
        line1="1 25544U 98067A   26234.00000000  .00000000  00000-0  00000-0 0  9991",
        line2="2 25544  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
        epoch=datetime.now(timezone.utc),
    )
    fields = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "MEAN_MOTION": 15.5,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 0.0000001,
    }
    refresh_group_from_omm([(element, None, fields)], group="tracked")
    status = cache_status_for_group("tracked")
    assert status["object_count"] >= 1
    assert status["source"] in {"CelesTrak", "cached"}


def test_status_reports_live_or_cached_only():
    status = cache_status_for_group("tracked", cached_rows=[])
    assert status["mode"] in {"CACHED", "LIVE", "DEMO"}
    assert "source" in status


def test_refresh_tracked_catalogs_keeps_valid_results_when_some_catalogs_fail(monkeypatch):
    from app.services.cache import refresh_tracked_catalogs

    def fake_fetch(catalog_number: int):
        if catalog_number == 25544:
            return (
                OrbitalElements(
                    name="ISS (ZARYA)",
                    catalog_number=25544,
                    line1="1 25544U 98067A   26234.00000000  .00000000  00000-0  00000-0 0  9991",
                    line2="2 25544  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
                    epoch=datetime.now(timezone.utc),
                ),
                None,
                {
                    "NORAD_CAT_ID": 25544,
                    "OBJECT_NAME": "ISS (ZARYA)",
                    "OBJECT_ID": "1998-067A",
                    "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "MEAN_MOTION": 15.5,
                    "ECCENTRICITY": 0.0001,
                    "INCLINATION": 51.64,
                    "RA_OF_ASC_NODE": 110.1,
                    "ARG_OF_PERICENTER": 40.2,
                    "MEAN_ANOMALY": 33.3,
                    "BSTAR": 1e-07,
                },
            )
        raise CelesTrakError("catalog blocked")

    monkeypatch.setattr("app.services.cache.resolve_catalogs_from_cache", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.services.cache.list_elements", lambda group, limit=2000: [])
    monkeypatch.setattr("app.services.cache.fetch_omm_by_catalog_number", fake_fetch)

    records, mode, status = refresh_tracked_catalogs(group="tracked", catalog_numbers=[25544, 22335])
    assert len(records) == 1
    assert records[0][0].catalog_number == 25544
    assert status["failed_objects"] >= 1


def test_refresh_is_required_when_cache_is_incomplete(monkeypatch):
    from app.services.cache import refresh_tracked_catalogs

    reset_cache()
    init_db()
    existing_rows = [{
        "catalog_number": 25544,
        "object_name": "ISS (ZARYA)",
        "line1": "1 25544U 98067A   26234.00000000  .00000000  00000-0  00000-0 0  9991",
        "line2": "2 25544  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
        "source_group": "tracked",
        "epoch": datetime.now(timezone.utc).isoformat(),
        "raw_json": '{"NORAD_CAT_ID":25544,"OBJECT_NAME":"ISS (ZARYA)","OBJECT_ID":"1998-067A","EPOCH":"2026-08-22T00:00:00Z","MEAN_MOTION":15.5,"ECCENTRICITY":0.0001,"INCLINATION":51.64,"RA_OF_ASC_NODE":110.1,"ARG_OF_PERICENTER":40.2,"MEAN_ANOMALY":33.3,"BSTAR":1e-07}',
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "last_successful_fetch": datetime.now(timezone.utc).isoformat(),
        "cache_fresh": 1,
    }]

    def fake_fetch(catalog_number: int):
        if catalog_number == 22335:
            return (
                OrbitalElements(
                    name="SL-16 DEB",
                    catalog_number=22335,
                    line1="1 22335U 92093Y   26234.00000000  .00000000  00000-0  00000-0 0  9991",
                    line2="2 22335  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
                    epoch=datetime.now(timezone.utc),
                ),
                None,
                {
                    "NORAD_CAT_ID": 22335,
                    "OBJECT_NAME": "SL-16 DEB",
                    "OBJECT_ID": "1992-093Y",
                    "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "MEAN_MOTION": 15.1,
                    "ECCENTRICITY": 0.0002,
                    "INCLINATION": 52.1,
                    "RA_OF_ASC_NODE": 111.1,
                    "ARG_OF_PERICENTER": 41.2,
                    "MEAN_ANOMALY": 34.3,
                    "BSTAR": 1e-07,
                },
            )
        raise CelesTrakError("catalog missing")

    def fake_cached_records(*args, **kwargs):
        return [(
            OrbitalElements(
                name="ISS (ZARYA)",
                catalog_number=25544,
                line1="1 25544U 98067A   26234.00000000  .00000000  00000-0  00000-0 0  9991",
                line2="2 25544  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
                epoch=datetime.now(timezone.utc),
            ),
            None,
            {
                "NORAD_CAT_ID": 25544,
                "OBJECT_NAME": "ISS (ZARYA)",
                "OBJECT_ID": "1998-067A",
                "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "MEAN_MOTION": 15.5,
                "ECCENTRICITY": 0.0001,
                "INCLINATION": 51.64,
                "RA_OF_ASC_NODE": 110.1,
                "ARG_OF_PERICENTER": 40.2,
                "MEAN_ANOMALY": 33.3,
                "BSTAR": 1e-07,
            },
        )]

    monkeypatch.setattr("app.services.cache.resolve_catalogs_from_cache", fake_cached_records)
    monkeypatch.setattr("app.services.cache.list_elements", lambda group, limit=2000: existing_rows)
    monkeypatch.setattr("app.services.cache.fetch_omm_by_catalog_number", fake_fetch)

    try:
        records, mode, status = refresh_tracked_catalogs(group="tracked", catalog_numbers=[25544, 22335])

        assert len(records) == 1
        assert records[0][0].catalog_number == 22335
        assert status["configured_objects"] == 2
    finally:
        reset_cache()


def test_omm_payload_can_propagate_without_tle_lines():
    payload = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "CLASSIFICATION_TYPE": "U",
        "EPOCH": "2026-08-22T11:00:00.000Z",
        "MEAN_MOTION": 15.5,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 1e-07,
        "EPHEMERIS_TYPE": 0,
        "ELEMENT_SET_NO": 999,
        "REV_AT_EPOCH": 99999,
    }
    sat = _satrec_from_omm_payload(payload)
    assert sat is not None
    trajectory = propagate_object(
        OrbitalElements(
            name="ISS (ZARYA)",
            catalog_number=25544,
            line1="",
            line2="",
            epoch=datetime.now(timezone.utc),
        ),
        start=datetime.now(timezone.utc),
        duration_minutes=1,
        step_seconds=60,
        satrec=sat,
    )
    assert len(trajectory) >= 2
    assert trajectory[0].x_km is not None


def test_refresh_group_from_omm_preserves_full_omm_payload():
    payload = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "CLASSIFICATION_TYPE": "U",
        "EPOCH": "2026-08-22T11:00:00.000Z",
        "MEAN_MOTION": 15.5,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 1e-07,
        "EPHEMERIS_TYPE": 0,
        "ELEMENT_SET_NO": 999,
        "REV_AT_EPOCH": 99999,
    }
    refresh_group_from_omm([(
        OrbitalElements(name="ISS (ZARYA)", catalog_number=25544, line1="", line2="", epoch=datetime.now(timezone.utc)),
        None,
        payload,
    )], group="tracked")
    with connect() as conn:
        row = conn.execute("SELECT raw_json FROM orbital_elements WHERE catalog_number=?", (25544,)).fetchone()
    assert row is not None
    stored = json.loads(row[0])
    assert stored["CLASSIFICATION_TYPE"] == "U"
    assert stored["MEAN_MOTION_DOT"] == 0.0


def test_get_object_trajectory_accepts_cached_sqlite_row():
    reset_cache()
    payload = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "CLASSIFICATION_TYPE": "U",
        "EPOCH": "2026-08-22T11:00:00.000Z",
        "MEAN_MOTION": 15.5,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 1e-07,
        "EPHEMERIS_TYPE": 0,
        "ELEMENT_SET_NO": 999,
        "REV_AT_EPOCH": 99999,
    }
    refresh_group_from_omm([(OrbitalElements(name="ISS (ZARYA)", catalog_number=25544, line1="", line2="", epoch=datetime.now(timezone.utc)), None, payload)], group="tracked")
    with connect() as conn:
        row = conn.execute("SELECT * FROM orbital_elements WHERE catalog_number=?", (25544,)).fetchone()
    result = get_object_trajectory(25544, duration_minutes=1, step_seconds=60, start_iso=datetime.now(timezone.utc).isoformat())
    assert result["catalog_number"] == 25544
    assert len(result["points"]) >= 2


def test_celestrak_http_error_captures_status_code(monkeypatch):
    class FakeResponse:
        status_code = 403
        text = "<!doctype html><html>blocked</html>"

        def raise_for_status(self):
            raise requests.HTTPError("403 Client Error: Forbidden")

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(CelesTrakError) as exc:
        from app.services.celestrak import fetch_group_omm

        fetch_group_omm(group="active")

    assert exc.value.status_code == 403
    assert "HTTP 403" in str(exc.value)


def test_list_cached_objects_and_propagation():
    reset_cache()
    init_db()
    element = OrbitalElements(
        name="ISS (ZARYA)",
        catalog_number=25544,
        line1="1 25544U 98067A   26234.00000000  .00000000  00000-0  00000-0 0  9991",
        line2="2 25544  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
        epoch=datetime.now(timezone.utc),
    )
    fields = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "MEAN_MOTION": 15.5,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 0.0000001,
    }
    refresh_group_from_omm([(element, None, fields)], group="tracked")
    objects = list_cached_objects(group="tracked")
    assert objects[0]["norad_id"] == 25544

    trajectory = propagate_object(element, start=datetime.now(timezone.utc), duration_minutes=5, step_seconds=60)
    assert len(trajectory) >= 2
    assert trajectory[0].timestamp is not None


def _make_element(catalog_number: int, name: str) -> OrbitalElements:
    base_line_1 = "1 25544U 98067A   26234.00000000  .00000000  00000-0  00000-0 0  9991"
    base_line_2 = "2 25544  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999"
    line1 = f"{base_line_1[:2]}{catalog_number:05d}{base_line_1[7:]}"
    line2 = f"{base_line_2[:2]}{catalog_number:05d}{base_line_2[7:]}"
    return OrbitalElements(name=name, catalog_number=catalog_number, line1=line1, line2=line2, epoch=datetime.now(timezone.utc))


def test_single_object_scan_returns_no_conjunction():
    start = datetime.now(timezone.utc)
    obj = _make_element(25544, "ISS (ZARYA)")
    events = scan_conjunctions([obj], start=start, config=ScanConfig(duration_minutes=90, coarse_step_seconds=60, screening_distance_km=10.0, max_objects=10, max_events=25))
    assert events == []


def test_near_zero_distance_pair_is_detected_and_relative_velocity_is_numeric():
    start = datetime.now(timezone.utc)
    a = _make_element(25544, "ISS A")
    b = _make_element(25545, "ISS B")
    event = find_closest_approach(a, b, start, duration_minutes=5, step_seconds=60, refinement_half_window_seconds=60)
    assert event.miss_distance_km >= 0.0
    assert event.relative_speed_km_s >= 0.0
    assert event.miss_distance_km < 0.1
    assert event.relative_speed_km_s < 1.0


def test_pair_deduplication_and_threshold_limit():
    start = datetime.now(timezone.utc)
    a = _make_element(25544, "ISS A")
    b = _make_element(25545, "ISS B")
    c = _make_element(25546, "ISS C")
    pairs = _candidate_pairs([a, b, c], start, ScanConfig(duration_minutes=5, coarse_step_seconds=60, screening_distance_km=10.0, max_objects=10, max_events=10))
    assert len(pairs) == 3

    events = scan_conjunctions([a, b, c], start=start, config=ScanConfig(duration_minutes=5, coarse_step_seconds=60, screening_distance_km=10.0, max_objects=10, max_events=10))
    assert len(events) >= 1


def test_propagation_failure_isolation_does_not_crash_scan():
    start = datetime.now(timezone.utc)
    good = _make_element(25544, "ISS GOOD")
    bad = OrbitalElements(name="BAD", catalog_number=99999, line1="BAD", line2="BAD", epoch=start)
    events = scan_conjunctions([good, bad], start=start, config=ScanConfig(duration_minutes=5, coarse_step_seconds=60, screening_distance_km=10.0, max_objects=10, max_events=10))
    assert events == []
