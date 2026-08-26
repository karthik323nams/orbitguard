from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_tracked_catalog_numbers  # noqa: E402
from app.services.celestrak import CelesTrakError, fetch_omm_by_catalog_number  # noqa: E402
from app.services.cache import cache_status_for_group, resolve_catalogs_from_cache  # noqa: E402
from app.services.scanner import ScanConfig, scan_conjunctions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a reproducible CATNR-based CelesTrak validation scan.")
    parser.add_argument("--catalogs", default="25544")
    parser.add_argument("--max-objects", type=int, default=20)
    parser.add_argument("--duration-minutes", type=int, default=30)
    parser.add_argument("--step-seconds", type=int, default=15)
    parser.add_argument("--screening-distance-km", type=float, default=50.0)
    parser.add_argument("--max-events", type=int, default=10)
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    if args.catalogs and args.catalogs.strip() != "":
        catalog_numbers = [int(part.strip()) for part in args.catalogs.split(",") if part.strip()]
    else:
        catalog_numbers = get_tracked_catalog_numbers()

    try:
        records = [fetch_omm_by_catalog_number(catalog_number) for catalog_number in catalog_numbers]
        mode = "LIVE"
        source = "CelesTrak"
    except (CelesTrakError, ValueError, RuntimeError):
        cached = resolve_catalogs_from_cache(catalog_numbers, group="tracked")
        if not cached:
            print(json.dumps({"validated_at_utc": started.isoformat(), "mode": "UNAVAILABLE", "source": "CelesTrak", "error": "No cached or live CATNR data available."}, indent=2))
            return 1
        records = cached
        mode = "CACHED"
        source = "SQLite cache"

    elements = [record[0] for record in records]
    satrecs = {record[0].catalog_number: record[1] for record in records}
    catalog_numbers_loaded = [e.catalog_number for e in elements]

    cfg = ScanConfig(
        duration_minutes=args.duration_minutes,
        coarse_step_seconds=args.step_seconds,
        screening_distance_km=args.screening_distance_km,
        max_relative_speed_bound_km_s=20.0,
        max_objects=args.max_objects,
        max_events=args.max_events,
    )

    events = scan_conjunctions(elements, start=started, config=cfg, satrecs=satrecs)

    report = {
        "validated_at_utc": started.isoformat(),
        "mode": mode,
        "source": source,
        "records_loaded": len(elements),
        "unique_catalog_numbers": len(set(catalog_numbers_loaded)),
        "duplicate_catalog_numbers": len(catalog_numbers_loaded) - len(set(catalog_numbers_loaded)),
        "catalog_numbers": catalog_numbers_loaded,
        "scan": {
            "duration_minutes": args.duration_minutes,
            "coarse_step_seconds": args.step_seconds,
            "screening_distance_km": args.screening_distance_km,
            "max_relative_speed_bound_km_s": cfg.max_relative_speed_bound_km_s,
            "effective_candidate_radius_km": round(
                cfg.screening_distance_km + cfg.max_relative_speed_bound_km_s * cfg.coarse_step_seconds, 3
            ),
        },
        "events_found": len(events),
        "events": [
            {
                "object_a": e.object_a_name,
                "catalog_a": e.object_a_catalog_number,
                "object_b": e.object_b_name,
                "catalog_b": e.object_b_catalog_number,
                "tca": e.closest_approach.isoformat(),
                "miss_distance_km": round(e.miss_distance_km, 3),
                "relative_speed_km_s": round(e.relative_speed_km_s, 3),
                "risk_score": e.risk_score,
                "risk_band": e.severity,
            }
            for e in events
        ],
        "checks": {
            "no_duplicate_catalog_numbers": len(catalog_numbers_loaded) == len(set(catalog_numbers_loaded)),
            "records_loaded_positive": len(elements) > 0,
            "catalog_numbers_support_modern_range": all(c >= 0 for c in catalog_numbers_loaded),
        },
        "cache_status": cache_status_for_group("tracked"),
        "notes": [
            "Validates the configured CATNR list, not GROUP=active.",
            "The discrete-time candidate screen uses a 20 km/s conservative relative-speed bound for its interval safety buffer.",
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
