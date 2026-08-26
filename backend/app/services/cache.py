from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sgp4.api import Satrec

from ..database.db import init_db, list_elements, upsert_elements
from ..models.orbital import OrbitalElements
from .celestrak import CelesTrakError, fetch_omm_by_catalog_number, validate_omm_record


def _parse_epoch(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _row_to_object(row: Any, group: str = "tracked") -> dict[str, Any]:
    payload = {}
    raw_json = row["raw_json"] if "raw_json" in row.keys() else "{}"
    raw_json = raw_json or "{}"
    try:
        payload = json.loads(raw_json) if raw_json else {}
    except json.JSONDecodeError:
        payload = {}
    return {
        "catalog_number": int(row["catalog_number"]),
        "norad_id": int(row["catalog_number"]),
        "name": row["object_name"] or f"CATALOG {row['catalog_number']}",
        "object_name": row["object_name"] or f"CATALOG {row['catalog_number']}",
        "source_group": row["source_group"] if "source_group" in row.keys() and row["source_group"] else group,
        "epoch": row["epoch"] if "epoch" in row.keys() else None,
        "fetched_at": row["fetched_at"] if "fetched_at" in row.keys() else None,
        "last_successful_fetch": row["last_successful_fetch"] if "last_successful_fetch" in row.keys() else None,
        "line1": row["line1"] if "line1" in row.keys() else None,
        "line2": row["line2"] if "line2" in row.keys() else None,
        "raw_json": payload,
        "cache_fresh": bool(row["cache_fresh"]) if "cache_fresh" in row.keys() else False,
    }


def refresh_group_from_omm(records, group: str) -> int:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for record in records:
        try:
            elements, _sat, fields = record
            validate_omm_record(fields)
        except (TypeError, ValueError, KeyError):
            continue
        payload = dict(fields)
        rows.append({
            "catalog_number": elements.catalog_number,
            "object_name": elements.name,
            "line1": elements.line1,
            "line2": elements.line2,
            "source_format": "OMM-JSON",
            "source_group": group,
            "epoch": payload.get("EPOCH") or (elements.epoch.isoformat() if elements.epoch else None),
            "raw_json": json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            "fetched_at": now,
            "last_successful_fetch": now,
            "cache_fresh": 1,
            "stale_after_seconds": 2 * 60 * 60,
        })
    return upsert_elements(rows)


def cached_group(group: str, limit: int = 250):
    init_db()
    return list_elements(group=group, limit=limit)


def list_cached_objects(group: str = "tracked", limit: int = 250):
    rows = cached_group(group, limit=limit)
    return [_row_to_object(row, group=group) for row in rows]


def resolve_catalogs_from_cache(catalog_numbers, group: str = "tracked"):
    init_db()
    rows = list_elements(group=group, limit=2000)
    catalog_set = {int(value) for value in catalog_numbers}
    results = []
    for row in rows:
        catalog_number = int(row["catalog_number"])
        if catalog_number not in catalog_set:
            continue
        line1 = row["line1"]
        line2 = row["line2"]
        if not line1 or not line2:
            continue
        try:
            sat = Satrec.twoline2rv(line1, line2)
        except Exception:
            continue
        raw_json = row["raw_json"] or "{}"
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            payload = {}
        element = OrbitalElements(
            name=str(row["object_name"] or f"CATALOG {catalog_number}"),
            catalog_number=catalog_number,
            line1=line1,
            line2=line2,
            epoch=_parse_epoch(row["epoch"]),
        )
        results.append((element, sat, payload))
    return results


def cache_status_for_group(
    group: str = "tracked",
    cached_rows: Optional[list[dict[str, Any]]] = None,
    stale_after_seconds: int = 2 * 60 * 60,
    configured_objects: Optional[int] = None,
):
    init_db()
    rows = cached_rows if cached_rows is not None else list_elements(group=group, limit=2000)
    if not rows:
        return {
            "mode": "DEMO",
            "source": "unavailable",
            "object_count": 0,
            "configured_objects": configured_objects if configured_objects is not None else 0,
            "loaded_objects": 0,
            "live_objects": 0,
            "cached_objects": 0,
            "failed_objects": configured_objects if configured_objects is not None else 0,
            "last_successful_fetch": None,
            "cache_age_seconds": None,
            "cache_fresh": False,
            "stale": True,
            "group": group,
        }

    timestamps = []
    for row in rows:
        value = row["last_successful_fetch"] or row["fetched_at"]
        if value:
            timestamps.append(value)
    latest = max(timestamps) if timestamps else None
    latest_dt = _parse_epoch(latest) if latest else None
    age_seconds = None if latest_dt is None else max(0.0, (datetime.now(timezone.utc) - latest_dt).total_seconds())
    loaded_objects = len(rows)
    configured_count = configured_objects if configured_objects is not None else loaded_objects
    dataset_complete = loaded_objects >= configured_count if configured_count else True
    fresh = (
        bool(latest_dt)
        and age_seconds is not None
        and age_seconds <= stale_after_seconds
        and dataset_complete
    )
    mode = "LIVE" if fresh else "CACHED"
    return {
        "mode": mode,
        "source": "CelesTrak" if fresh or latest else "unavailable",
        "object_count": loaded_objects,
        "configured_objects": configured_count,
        "loaded_objects": loaded_objects,
        "live_objects": loaded_objects if fresh else 0,
        "cached_objects": loaded_objects if not fresh else 0,
        "failed_objects": max(0, configured_count - loaded_objects),
        "last_successful_fetch": latest,
        "cache_age_seconds": round(float(age_seconds), 1) if age_seconds is not None else None,
        "cache_fresh": fresh,
        "stale": not fresh,
        "group": group,
    }


def refresh_tracked_catalogs(group: str = "tracked", catalog_numbers: Optional[list[int]] = None):
    from ..config import get_tracked_catalog_numbers, get_tracked_group
    from .celestrak import fetch_group_omm

    chosen = catalog_numbers or get_tracked_catalog_numbers()
    cached = resolve_catalogs_from_cache(chosen, group=group)
    existing_cache = list_elements(group=group, limit=2000)
    status = cache_status_for_group(group, cached_rows=existing_cache, configured_objects=len(chosen))
    cache_complete = status["configured_objects"] == 0 or status["object_count"] >= status["configured_objects"]
    if cached and not status["stale"] and cache_complete:
        return cached, "LIVE", status

    if catalog_numbers is None:
        try:
            tracked_group = get_tracked_group()
            group_candidates = [tracked_group] if tracked_group else []
            if group not in (None, "", "tracked") and group != tracked_group:
                group_candidates.insert(0, group)
            if tracked_group == "tracked":
                group_candidates = ["active", "tracked"]

            for candidate in group_candidates:
                try:
                    live_group_records = fetch_group_omm(group=candidate, max_objects=len(chosen) if chosen else None)
                except (CelesTrakError, ValueError, RuntimeError):
                    continue
                if not live_group_records:
                    continue
                refresh_group_from_omm(live_group_records, group=group)
                final_status = cache_status_for_group(group, cached_rows=list_elements(group=group, limit=2000), configured_objects=len(chosen))
                if final_status["cache_fresh"]:
                    return live_group_records, "LIVE", final_status
                return live_group_records, "CACHED", final_status
        except (CelesTrakError, ValueError, RuntimeError):
            pass

    live_records = []
    failures = []
    for catalog_number in chosen:
        try:
            live_records.append(fetch_omm_by_catalog_number(catalog_number))
        except (CelesTrakError, ValueError, RuntimeError):
            failures.append(catalog_number)

    if live_records:
        refresh_group_from_omm(live_records, group=group)
        final_status = cache_status_for_group(group, cached_rows=list_elements(group=group, limit=2000), configured_objects=len(chosen))
        if final_status["cache_fresh"]:
            return live_records, "LIVE", final_status
        return live_records, "CACHED", final_status

    if cached:
        return cached, "CACHED", status

    if failures:
        raise CelesTrakError(f"Unable to fetch validated OMM payloads for catalog(s): {', '.join(str(c) for c in failures)}")

    raise CelesTrakError(f"No valid responses were returned for group {group!r}.")
