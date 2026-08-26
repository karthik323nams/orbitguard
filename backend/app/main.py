from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sgp4 import omm
from sgp4.api import Satrec

from .config import get_tracked_catalog_numbers, get_tracked_group
from .database.db import get_launch_metadata, init_db, save_launch_metadata
from .database.history import (
    create_scan_run,
    init_history_db,
    list_pair_history,
    recent_scan_runs,
    save_conjunction_observations,
)
from .models.orbital import OrbitalElements
from .services.cache import (
    cache_status_for_group,
    cached_group,
    list_cached_objects,
    refresh_group_from_omm,
    refresh_tracked_catalogs,
    resolve_catalogs_from_cache,
)
from .services.celestrak import CelesTrakError, fetch_group_omm, fetch_omm_by_catalog_number, fetch_satcat_by_catalog_number
from .services.conjunction import find_closest_approach
from .services.frames import ecef_to_geodetic, teme_to_ecef
from .services.propagation import (
    apogee_perigee_km,
    classify_orbit_regime,
    orbital_period_minutes,
    propagate,
    propagate_forward,
    propagate_object,
)
from .services.scanner import ScanConfig, _candidate_pairs, scan_conjunctions
from .services.visualization import trajectory_window

app = FastAPI(title="Astrail", version="1.0.0")
_default_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://10.211.60.96:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "http://10.211.60.96:5176",
    "http://0.0.0.0:5176",
]
_env_cors_origins = os.getenv("ORBITGUARD_CORS_ORIGINS")
allowed_origins = [
    origin.strip()
    for origin in ("_" if _env_cors_origins is None else _env_cors_origins).split(",")
    if origin.strip()
] if _env_cors_origins else _default_cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    init_history_db()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_catalog(value: Union[str, int]) -> int:
    raw = str(value).strip()
    if not re.fullmatch(r"\d{1,9}", raw):
        raise HTTPException(status_code=400, detail=f"Invalid catalog ID: {value!r}")
    return int(raw)


def _as_catalog_object(row: dict[str, Any]) -> OrbitalElements:
    epoch = row["epoch"] if "epoch" in row.keys() else None
    epoch_dt = None
    if epoch:
        try:
            epoch_dt = datetime.fromisoformat(str(epoch).replace("Z", "+00:00"))
        except ValueError:
            epoch_dt = None
    return OrbitalElements(
        name=str(row["object_name"] if row["object_name"] else f"CATALOG {row['catalog_number']}"),
        catalog_number=int(row["catalog_number"]),
        line1=str(row["line1"] if row["line1"] else ""),
        line2=str(row["line2"] if row["line2"] else ""),
        epoch=epoch_dt,
    )


def _normalize_omm_epoch(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1]
        if "+" in text or text.count(":") >= 2:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            text = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
        elif "T" in text and "." not in text:
            text = f"{text}.000"
        return text
    except ValueError:
        return text


def _satrec_from_omm_payload(raw_payload: Any) -> Optional[Satrec]:
    if not isinstance(raw_payload, dict):
        return None
    payload = dict(raw_payload)
    epoch = _normalize_omm_epoch(payload.get("EPOCH"))
    if epoch is not None:
        payload["EPOCH"] = epoch
    try:
        sat = Satrec()
        omm.initialize(sat, payload)
        return sat
    except (TypeError, ValueError, RuntimeError, KeyError):
        return None


def _serialize_event(event, *, now: Optional[datetime] = None, trend: Optional[str] = None, data_age_minutes: Optional[float] = None) -> dict[str, Any]:
    now = now or _utc_now()
    time_to_tca = max(0.0, (event.closest_approach - now).total_seconds() / 60.0)
    breakdown = event.risk_breakdown or {}
    event_id = getattr(event, "id", None) or f"{event.object_a_catalog_number}-{event.object_b_catalog_number}-{event.closest_approach.isoformat()}"
    return {
        "id": event_id,
        "object_a": {"norad_id": int(event.object_a_catalog_number), "name": event.object_a_name},
        "object_b": {"norad_id": int(event.object_b_catalog_number), "name": event.object_b_name},
        "catalog_a": str(event.object_a_catalog_number),
        "name_a": event.object_a_name,
        "catalog_b": str(event.object_b_catalog_number),
        "name_b": event.object_b_name,
        "tca": event.closest_approach.isoformat(),
        "miss_distance_km": round(float(event.miss_distance_km), 3),
        "relative_velocity_km_s": round(float(event.relative_speed_km_s), 3),
        "risk_score": round(float(event.risk_score), 1),
        "risk_band": (event.severity or "LOW").upper(),
        "risk_level": (event.severity or "LOW").upper(),
        "priority_score": round(float(event.risk_score), 1),
        "threshold_km": 10.0,
        "time_to_tca_minutes": round(time_to_tca, 1),
        "trend": trend or "NEW",
        "data_age_minutes": round(float(data_age_minutes or 0.0), 1),
        "risk_breakdown": {
            "miss_distance_score": round(float(breakdown.get("miss_distance_score", 0)), 1),
            "imminence_score": round(float(breakdown.get("imminence_score", 0)), 1),
            "relative_speed_score": round(float(breakdown.get("relative_speed_score", 0)), 1),
            "freshness_score": round(float(breakdown.get("freshness_score", 0)), 1),
            "reasons": list(breakdown.get("reasons", [])),
            "uncertainty_status": str(breakdown.get("uncertainty_status") or "Not available in GP element set; score is prioritization only"),
        },
    }


def _classify_trend(latest: dict[str, Any], previous: Optional[dict[str, Any]]) -> str:
    if previous is None:
        return "NEW"
    risk_delta = float(latest.get("risk_score", 0.0)) - float(previous.get("risk_score", 0.0))
    previous_miss = float(previous.get("miss_distance_km", 0.0))
    latest_miss = float(latest.get("miss_distance_km", 0.0))
    miss_delta = previous_miss - latest_miss
    if risk_delta > 5 or miss_delta > previous_miss * 0.10:
        return "WORSENING"
    if risk_delta < -5 or latest_miss > previous_miss * 1.10:
        return "IMPROVING"
    return "STABLE"


def _normalize_group(group: Optional[str]) -> str:
    if group in (None, "", "active", "tracked"):
        return "tracked"
    return group


def _load_group_records(group: str, max_objects: Optional[int] = None) -> list[tuple[OrbitalElements, Any, dict[str, Any]]]:
    group = _normalize_group(group)
    if group in {"tracked", "active"}:
        catalog_numbers = get_tracked_catalog_numbers()[: max_objects] if max_objects is not None else get_tracked_catalog_numbers()
        cached = resolve_catalogs_from_cache(catalog_numbers, group=group)
        if cached:
            status = cache_status_for_group(group)
            if not status["stale"]:
                return cached

        tracked_group = get_tracked_group()
        if tracked_group and tracked_group != group:
            try:
                live_group_records = fetch_group_omm(group=tracked_group, max_objects=max_objects)
                if live_group_records:
                    refresh_group_from_omm(live_group_records, group=group)
                    return live_group_records
            except (CelesTrakError, ValueError, RuntimeError):
                pass

        try:
            records, mode, status_info = refresh_tracked_catalogs(group=group, catalog_numbers=catalog_numbers)
            if records:
                return records
        except (CelesTrakError, ValueError, RuntimeError):
            if cached:
                return cached
            raise

        if cached:
            return cached

    return fetch_group_omm(group=group, max_objects=max_objects)


def _cached_records(group: str, limit: int = 250) -> list[tuple[OrbitalElements, Any, dict[str, Any]]]:
    rows = cached_group(group, limit=limit)
    results: list[tuple[OrbitalElements, Any, dict[str, Any]]] = []
    for row in rows:
        line1 = row["line1"] if row["line1"] else None
        line2 = row["line2"] if row["line2"] else None
        if line1 and line2:
            obj = _as_catalog_object(row)
            from sgp4.api import Satrec

            sat = Satrec.twoline2rv(line1, line2)
            raw = json.loads(row["raw_json"] or "{}") if row["raw_json"] else {}
            results.append((obj, sat, raw))
    return results


@app.get("/health")
def health() -> dict[str, str]:
    status = cache_status_for_group("tracked")
    mode = status["mode"].lower()
    return {"status": "ok", "service": "astrail-api", "version": "1.0.0", "data_mode": mode}


@app.get("/data/status")
def data_status(group: str = "tracked"):
    status = cache_status_for_group(_normalize_group(group))
    return {
        "mode": status["mode"],
        "source": status["source"],
        "object_count": status["object_count"],
        "last_successful_fetch": status["last_successful_fetch"],
        "cache_age_seconds": status["cache_age_seconds"],
        "cache_fresh": status["cache_fresh"],
        "stale": status["stale"],
        "group": status["group"],
    }


@app.get("/data/cache")
def data_cache(group: str = "tracked", limit: int = 100):
    rows = cached_group(_normalize_group(group), limit=limit)
    objects = []
    for row in rows:
        epoch = row["epoch"] if row["epoch"] else None
        raw = json.loads(row["raw_json"] or "{}") if row["raw_json"] else {}
        if epoch:
            try:
                dt = datetime.fromisoformat(str(epoch).replace("Z", "+00:00")).astimezone(timezone.utc)
                data_age_minutes = max(0.0, (_utc_now() - dt).total_seconds() / 60.0)
            except ValueError:
                data_age_minutes = 0.0
        else:
            data_age_minutes = 0.0
        objects.append(
            {
                "catalog_number": str(row["catalog_number"]),
                "name": row["object_name"],
                "object_id": raw.get("OBJECT_ID") or f"{row['catalog_number']}",
                "source_group": row["source_group"] if row["source_group"] else group,
                "epoch": epoch,
                "data_age_minutes": round(data_age_minutes, 1),
                "raw_omm": raw,
            }
        )
    return {"group": group, "count": len(objects), "objects": objects}


@app.get("/objects")
def list_objects(group: str = "tracked", limit: int = 100):
    group = _normalize_group(group)
    objects = list_cached_objects(group=group, limit=max(1, min(limit, 500)))
    return {
        "group": group,
        "count": len(objects),
        "objects": objects,
    }


@app.get("/objects/{norad_id}")
def get_object(norad_id: int, group: str = "tracked"):
    group = _normalize_group(group)
    rows = cached_group(group, limit=2000)
    for row in rows:
        if int(row["catalog_number"]) == int(norad_id):
            payload = json.loads(row["raw_json"] or "{}") if row["raw_json"] else {}
            return {
                "catalog_number": int(row["catalog_number"]),
                "norad_id": int(row["catalog_number"]),
                "name": row["object_name"],
                "source_group": row["source_group"] or group,
                "epoch": row["epoch"],
                "fetched_at": row["fetched_at"],
                "last_successful_fetch": row["last_successful_fetch"],
                "raw_omm": payload,
            }
    raise HTTPException(status_code=404, detail=f"Object {norad_id} not found in group {group!r}")


@app.get("/objects/{norad_id}/trajectory")
def get_object_trajectory(
    norad_id: int,
    group: str = "tracked",
    duration_minutes: int = Query(60, ge=1, le=1440),
    step_seconds: int = Query(60, ge=1, le=3600),
    start_iso: Optional[str] = Query(None),
):
    group = _normalize_group(group)
    rows = cached_group(group, limit=2000)
    match = None
    for row in rows:
        if int(row["catalog_number"]) == int(norad_id):
            match = row
            break
    if match is None:
        raise HTTPException(status_code=404, detail=f"Object {norad_id} not found in group {group!r}")

    element = _as_catalog_object(match)
    raw_json = match["raw_json"] if "raw_json" in match.keys() else None
    payload = json.loads(raw_json or "{}") if raw_json else {}
    satrec = None
    if not (element.line1 and element.line2):
        satrec = _satrec_from_omm_payload(payload)
    if satrec is None and not (element.line1 and element.line2):
        raise HTTPException(status_code=500, detail=f"Trajectory unavailable for object {norad_id}: missing TLE or OMM payload")
    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00")) if start_iso else datetime.now(timezone.utc)
    trajectory = propagate_object(
        element,
        start=start,
        duration_minutes=duration_minutes,
        step_seconds=step_seconds,
        satrec=satrec,
    )
    return {
        "catalog_number": element.catalog_number,
        "norad_id": element.catalog_number,
        "name": element.name,
        "start": start.isoformat(),
        "duration_minutes": duration_minutes,
        "step_seconds": step_seconds,
        "points": [
            {
                "timestamp": point.timestamp.isoformat(),
                "position_km": [round(float(point.x_km), 6), round(float(point.y_km), 6), round(float(point.z_km), 6)],
                "velocity_km_s": [round(float(point.vx_km_s), 6), round(float(point.vy_km_s), 6), round(float(point.vz_km_s), 6)],
            }
            for point in trajectory
        ],
    }


def _parse_cospar_id(cospar_id: str) -> dict:
    """
    Parse a COSPAR ID of the form YYYY-NNNP (e.g. '1998-067A') into components.
    Returns dict with launch_year, launch_number (int), piece (str).
    Returns empty dict if parsing fails.
    """
    import re as _re
    if not cospar_id:
        return {}
    m = _re.match(r"^(\d{4})-(\d{1,4})([A-Z]*)$", str(cospar_id).strip().upper())
    if not m:
        return {}
    return {
        "launch_year": int(m.group(1)),
        "launch_number": int(m.group(2)),
        "piece": m.group(3) or "A",
    }


_OWNER_CODES = {
    "US": "United States",
    "CIS": "Russia/CIS",
    "PRC": "China",
    "IND": "India",
    "ESA": "European Space Agency",
    "JAP": "Japan",
    "FR": "France",
    "UK": "United Kingdom",
    "GER": "Germany",
    "IT": "Italy",
    "CA": "Canada",
    "AUS": "Australia",
    "BR": "Brazil",
    "ISS": "International Space Station",
    "EUME": "EUMETSAT",
    "SES": "SES S.A.",
    "GLOB": "Globalstar",
    "ORB": "ORBCOMM",
    "IRID": "Iridium",
    "ARB": "Arab Satellite Communications",
    "KOR": "South Korea",
    "SPA": "Spain",
    "NICO": "Cyprus",
    "AB": "Arab League",
    "AC": "Asia-Pacific",
    "AGO": "Angola",
    "ARG": "Argentina",
    "ASRE": "Asian Space Research",
    "AUT": "Austria",
    "AZER": "Azerbaijan",
    "BEL": "Belgium",
    "BGD": "Bangladesh",
    "BHRN": "Bahrain",
    "BOL": "Bolivia",
    "BTR": "Belarus",
    "BUL": "Bulgaria",
    "CHLE": "Chile",
    "COL": "Colombia",
    "CRI": "Costa Rica",
    "CZCH": "Czech Republic",
    "DEN": "Denmark",
    "ECU": "Ecuador",
    "EGYP": "Egypt",
    "EST": "Estonia",
    "ETH": "Ethiopia",
    "FIN": "Finland",
    "GHA": "Ghana",
    "GRC": "Greece",
    "GAT": "Guatemala",
    "HUN": "Hungary",
    "IDN": "Indonesia",
    "IRN": "Iran",
    "IRQ": "Iraq",
    "ISR": "Israel",
    "JOR": "Jordan",
    "KAZ": "Kazakhstan",
    "KEN": "Kenya",
    "LAO": "Laos",
    "LBY": "Libya",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "MA": "Morocco",
    "MYS": "Malaysia",
    "MEX": "Mexico",
    "MNG": "Mongolia",
    "MMR": "Myanmar",
    "NLD": "Netherlands",
    "NOR": "Norway",
    "NPL": "Nepal",
    "NZL": "New Zealand",
    "NGA": "Nigeria",
    "PAK": "Pakistan",
    "PAN": "Panama",
    "PER": "Peru",
    "PHL": "Philippines",
    "POL": "Poland",
    "POR": "Portugal",
    "QAT": "Qatar",
    "ROM": "Romania",
    "Rwa": "Rwanda",
    "SAUD": "Saudi Arabia",
    "SGP": "Singapore",
    "SLK": "Slovakia",
    "SVN": "Slovenia",
    "SAF": "South Africa",
    "LKA": "Sri Lanka",
    "SWE": "Sweden",
    "SUI": "Switzerland",
    "TWN": "Taiwan",
    "THA": "Thailand",
    "TUR": "Turkey",
    "UAE": "United Arab Emirates",
    "UKR": "Ukraine",
    "URY": "Uruguay",
    "VEN": "Venezuela",
    "VNM": "Vietnam",
    "ZWE": "Zimbabwe"
}

_LAUNCH_SITES = {
    "AFETR": "Cape Canaveral Space Force Station, Florida, USA",
    "AFWTR": "Vandenberg Space Force Base, California, USA",
    "TYMSC": "Baikonur Cosmodrome, Kazakhstan",
    "JSC": "Jiuquan Satellite Launch Center, China",
    "SDSC": "Satish Dhawan Space Centre, Sriharikota, India",
    "KSCUT": "Uchinoura Space Center, Japan",
    "Kourou": "Guiana Space Centre, French Guiana",
    "CSG": "Guiana Space Centre, French Guiana",
    "PLMSC": "Plesetsk Cosmodrome, Russia",
    "SVOB": "Vostochny Cosmodrome, Russia",
    "WS": "Woomera Test Range, Australia",
    "XSLC": "Xichang Satellite Launch Center, China",
    "TSLC": "Taiyuan Satellite Launch Center, China",
    "Wenchang": "Wenchang Space Launch Site, China",
    "WSMR": "White Sands Missile Range, USA",
    "WFF": "Wallops Flight Facility, Virginia, USA",
    "KSC": "Kennedy Space Center, Florida, USA",
    "VOSTO": "Vostochny Cosmodrome, Russia",
    "Sge": "Semnan Launch Site, Iran",
    "SEML": "Semnan Launch Site, Iran",
    "YUN": "Sohae Satellite Launching Station, North Korea",
    "PALB": "Palamachims, Israel",
    "TNSC": "Tanegashima Space Center, Japan",
    "YOS": "Naro Space Center, South Korea",
    "KWAJ": "Kwajalein Atoll, Marshall Islands",
    "HAW": "Hawaii Launch Site, USA",
    "DOM": "Dombarovsky Air Base, Russia",
    "KAPUS": "Kapustin Yar Cosmodrome, Russia",
    "SVO": "Svobodny Cosmodrome, Russia",
}


def _resolve_owner_name(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    code_upper = code.strip().upper()
    return _OWNER_CODES.get(code_upper, code)


def _resolve_launch_site_name(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    code_upper = code.strip().upper()
    return _LAUNCH_SITES.get(code_upper, code)


def _build_satellite_profile(row: dict, group: str = "tracked") -> dict:
    """
    Build a structured satellite profile from a cached DB row.
    Does not make any external API calls — all data is derived from the stored OMM payload.
    """
    raw = json.loads(row["raw_json"] or "{}") if row.get("raw_json") else {}

    # --- Identity ---
    norad_id = int(row["catalog_number"])
    name = row["object_name"] or f"CATALOG {norad_id}"
    cospar_id = str(raw.get("OBJECT_ID") or "").strip()
    object_type = str(raw.get("OBJECT_TYPE") or "").strip() or None

    # --- Orbital state from OMM ---
    def _float(key: str, default: float = 0.0) -> Optional[float]:
        val = raw.get(key)
        if val in (None, ""):
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    mean_motion = _float("MEAN_MOTION")  # rev/day
    eccentricity = _float("ECCENTRICITY") or 0.0
    inclination = _float("INCLINATION")
    epoch_str = str(raw.get("EPOCH") or row.get("epoch") or "").strip() or None

    period_min: Optional[float] = None
    apogee_km: Optional[float] = None
    perigee_km: Optional[float] = None
    orbit_regime: Optional[str] = None

    if mean_motion is not None and mean_motion > 0:
        period_min = round(orbital_period_minutes(mean_motion), 2)
        ap, pe = apogee_perigee_km(mean_motion, eccentricity)
        apogee_km = ap
        perigee_km = pe
        orbit_regime = classify_orbit_regime(mean_motion, eccentricity, inclination or 0.0)

    orbital_state = {
        "epoch": epoch_str,
        "mean_motion_rev_day": mean_motion,
        "eccentricity": eccentricity,
        "inclination_deg": inclination,
        "ra_of_asc_node_deg": _float("RA_OF_ASC_NODE"),
        "arg_of_pericenter_deg": _float("ARG_OF_PERICENTER"),
        "period_minutes": period_min,
        "apogee_km": apogee_km,
        "perigee_km": perigee_km,
        "orbit_regime": orbit_regime,
    }

    # --- Current position (live SGP4 propagation) ---
    current_position: Optional[dict] = None
    try:
        element = _as_catalog_object(row)
        satrec: Optional[object] = None
        if not (element.line1 and element.line2):
            satrec = _satrec_from_omm_payload(raw)
        now_ts = _utc_now()
        state = propagate(element, now_ts, satrec=satrec)
        ex, ey, ez = teme_to_ecef(state.x_km, state.y_km, state.z_km, state.timestamp)
        lat, lon, alt = ecef_to_geodetic(ex, ey, ez)
        velocity_mag = round(
            float((state.vx_km_s**2 + state.vy_km_s**2 + state.vz_km_s**2) ** 0.5), 4
        )
        current_position = {
            "timestamp": now_ts.isoformat(),
            "lat_deg": round(float(lat), 4),
            "lon_deg": round(float(lon), 4),
            "alt_km": round(float(alt), 2),
            "velocity_km_s": velocity_mag,
            "teme_x_km": round(float(state.x_km), 3),
            "teme_y_km": round(float(state.y_km), 3),
            "teme_z_km": round(float(state.z_km), 3),
        }
    except Exception:
        current_position = None

    # Check if launch metadata is in DB
    db_launch = get_launch_metadata(norad_id)
    if not db_launch:
        # Try to fetch from Celestrak SATCAT
        try:
            record = fetch_satcat_by_catalog_number(norad_id)
            if record:
                # Verify that COSPAR ID matches to avoid conflicts with synthetic test objects
                satcat_cospar = str(record.get("OBJECT_ID") or "").strip()
                gp_cospar = str(cospar_id or "").strip()
                if gp_cospar and satcat_cospar and gp_cospar != satcat_cospar:
                    record = None

            if record:
                db_launch = {
                    "catalog_number": norad_id,
                    "cospar_id": record.get("OBJECT_ID") or cospar_id,
                    "launch_date": record.get("LAUNCH_DATE"),
                    "launch_site_code": record.get("LAUNCH_SITE"),
                    "launch_site_name": _resolve_launch_site_name(record.get("LAUNCH_SITE")),
                    "owner_code": record.get("OWNER"),
                    "owner_name": _resolve_owner_name(record.get("OWNER")),
                    "launch_vehicle": None,
                    "fetched_at": _utc_now().isoformat(),
                }
                save_launch_metadata(db_launch)
        except Exception:
            db_launch = None

    cospar_parsed = _parse_cospar_id(cospar_id)

    if db_launch:
        launch_metadata = {
            "cospar_id": db_launch.get("cospar_id") or cospar_id or None,
            "launch_year": cospar_parsed.get("launch_year"),
            "launch_number": cospar_parsed.get("launch_number"),
            "piece": cospar_parsed.get("piece"),
            "country": db_launch.get("owner_name") or db_launch.get("owner_code"),
            "launch_date": db_launch.get("launch_date"),
            "launch_site": db_launch.get("launch_site_name") or db_launch.get("launch_site_code"),
            "launch_vehicle": db_launch.get("launch_vehicle"),
            "data_note": "Launch metadata retrieved from CelesTrak SATCAT catalog.",
        }
    else:
        launch_metadata = {
            "cospar_id": cospar_id or None,
            "launch_year": cospar_parsed.get("launch_year"),
            "launch_number": cospar_parsed.get("launch_number"),
            "piece": cospar_parsed.get("piece"),
            "country": None,
            "launch_date": None,
            "launch_site": None,
            "launch_vehicle": None,
            "data_note": "Launch site, country, and vehicle are not available offline.",
        }


    # --- Tracking status ---
    last_fetch = row.get("last_successful_fetch") or row.get("fetched_at")
    data_age_minutes: Optional[float] = None
    if last_fetch:
        try:
            fetch_dt = datetime.fromisoformat(str(last_fetch).replace("Z", "+00:00")).astimezone(timezone.utc)
            data_age_minutes = round(max(0.0, (_utc_now() - fetch_dt).total_seconds() / 60.0), 1)
        except ValueError:
            pass

    tracking_status = {
        "data_mode": "LIVE" if (data_age_minutes is not None and data_age_minutes < 120) else "CACHED",
        "last_updated": last_fetch,
        "data_age_minutes": data_age_minutes,
        "source": "CelesTrak GP",
    }

    return {
        "identity": {
            "name": name,
            "norad_id": norad_id,
            "cospar_id": cospar_id or None,
            "object_type": object_type,
        },
        "orbital_state": orbital_state,
        "current_position": current_position,
        "launch_metadata": launch_metadata,
        "tracking_status": tracking_status,
    }


@app.get("/objects/{norad_id}/profile")
def get_object_profile(norad_id: int, group: str = "tracked"):
    """
    Return a structured satellite profile assembling identity, orbital state,
    current live position, launch metadata (from COSPAR ID), and tracking status.
    All data is derived from the stored CelesTrak OMM payload — no external API calls.
    """
    group = _normalize_group(group)
    rows = cached_group(group, limit=2000)
    for row in rows:
        if int(row["catalog_number"]) == int(norad_id):
            profile = _build_satellite_profile(dict(row), group=group)
            return profile
    raise HTTPException(status_code=404, detail=f"Object {norad_id} not found in group {group!r}")


@app.get("/objects/{norad_id}/full-orbit")
def get_object_full_orbit(
    norad_id: int,
    group: str = "tracked",
    step_seconds: Optional[int] = Query(None, ge=10, le=3600),
):
    """
    Propagate the satellite through exactly one complete orbital period,
    centered around the satellite's current position (start = now - T/2).
    The orbital period is derived from MEAN_MOTION in the stored OMM payload.
    Returns TEME trajectory + current geodetic position.
    """
    group = _normalize_group(group)
    rows = cached_group(group, limit=2000)
    match = None
    for row in rows:
        if int(row["catalog_number"]) == int(norad_id):
            match = row
            break
    if match is None:
        raise HTTPException(status_code=404, detail=f"Object {norad_id} not found in group {group!r}")

    raw_json = match["raw_json"] if "raw_json" in match.keys() else None
    payload = json.loads(raw_json or "{}") if raw_json else {}

    # Determine orbital period from MEAN_MOTION
    mean_motion_raw = payload.get("MEAN_MOTION")
    try:
        mean_motion = float(mean_motion_raw) if mean_motion_raw not in (None, "") else 0.0
    except (TypeError, ValueError):
        mean_motion = 0.0

    period_min = orbital_period_minutes(mean_motion) if mean_motion > 0 else 90.0

    # Auto step: aim for ~120 sample points per orbit (min 30s, max 300s)
    auto_step = max(30, min(300, int(period_min * 60 / 120)))
    if not isinstance(step_seconds, int):
        step_seconds = None
    resolved_step = step_seconds if step_seconds is not None else auto_step

    # Start half a period before now so current position is near the middle
    now = _utc_now()
    orbit_start = now - timedelta(minutes=period_min / 2)

    element = _as_catalog_object(match)
    satrec = None
    if not (element.line1 and element.line2):
        satrec = _satrec_from_omm_payload(payload)
    if satrec is None and not (element.line1 and element.line2):
        raise HTTPException(
            status_code=500,
            detail=f"Full-orbit trajectory unavailable for {norad_id}: missing TLE or OMM payload",
        )

    # Propagate one full orbital period
    orbit_duration_min = int(math.ceil(period_min)) + 1  # +1 min buffer to close the loop
    samples = propagate_forward(
        element, orbit_start, orbit_duration_min, resolved_step, satrec=satrec
    )

    # Current position
    current_position: Optional[dict] = None
    try:
        state_now = propagate(element, now, satrec=satrec)
        ex, ey, ez = teme_to_ecef(state_now.x_km, state_now.y_km, state_now.z_km, state_now.timestamp)
        lat, lon, alt = ecef_to_geodetic(ex, ey, ez)
        velocity_mag = round(
            float((state_now.vx_km_s**2 + state_now.vy_km_s**2 + state_now.vz_km_s**2) ** 0.5), 4
        )
        current_position = {
            "timestamp": now.isoformat(),
            "x_km": round(float(state_now.x_km), 3),
            "y_km": round(float(state_now.y_km), 3),
            "z_km": round(float(state_now.z_km), 3),
            "lat_deg": round(float(lat), 4),
            "lon_deg": round(float(lon), 4),
            "alt_km": round(float(alt), 2),
            "velocity_km_s": velocity_mag,
        }
    except Exception:
        current_position = None

    return {
        "catalog_number": element.catalog_number,
        "norad_id": element.catalog_number,
        "name": element.name,
        "frame": "TEME",
        "orbital_period_minutes": round(period_min, 2),
        "step_seconds": resolved_step,
        "orbit_start": orbit_start.isoformat(),
        "orbit_end": (orbit_start + timedelta(minutes=orbit_duration_min)).isoformat(),
        "current_position": current_position,
        "points": [
            {
                "timestamp": pt.timestamp.isoformat(),
                "x_km": round(float(pt.x_km), 3),
                "y_km": round(float(pt.y_km), 3),
                "z_km": round(float(pt.z_km), 3),
                "vx_km_s": round(float(pt.vx_km_s), 4),
                "vy_km_s": round(float(pt.vy_km_s), 4),
                "vz_km_s": round(float(pt.vz_km_s), 4),
            }
            for pt in samples
        ],
    }


@app.get("/data/refresh")
def refresh_data(group: str = "tracked", max_objects: int = 500):
    group = _normalize_group(group)
    if max_objects <= 0 or max_objects > 2000:
        raise HTTPException(status_code=400, detail="max_objects must be between 1 and 2000")

    catalog_numbers = get_tracked_catalog_numbers()[:max_objects]
    cached_rows = cached_group(group, limit=max_objects)
    try:
        records, mode, status_info = refresh_tracked_catalogs(group=group, catalog_numbers=catalog_numbers)
        written = refresh_group_from_omm(records, group=group)
        refreshed_at = _utc_now()
        return {
            "status": "ok" if mode == "LIVE" else "cached",
            "mode": mode,
            "group": group,
            "records_fetched": len(records),
            "records_stored": written,
            "refreshed_at": refreshed_at.isoformat(),
            "next_allowed_refresh_at": (refreshed_at + timedelta(hours=2)).isoformat(),
            "source": "CelesTrak",
            "last_successful_fetch": status_info["last_successful_fetch"],
            "cache_fresh": status_info["cache_fresh"],
            "object_count": status_info["object_count"],
            "configured_objects": status_info["configured_objects"],
            "failed_objects": status_info["failed_objects"],
        }
    except (CelesTrakError, ValueError, RuntimeError) as exc:
        if cached_rows:
            return {
                "status": "cached",
                "mode": "CACHED",
                "group": group,
                "records_fetched": 0,
                "records_stored": len(cached_rows),
                "refreshed_at": _utc_now().isoformat(),
                "next_allowed_refresh_at": (_utc_now() + timedelta(hours=2)).isoformat(),
                "note": f"CelesTrak unavailable; serving the local cache: {exc}",
                "source": "CelesTrak",
            }
        raise HTTPException(status_code=503, detail=f"Unable to refresh {group!r}: {exc}") from exc


def _prepare_screening_objects(records: list[tuple[OrbitalElements, Any, dict[str, Any]]], *, start: datetime) -> tuple[list[OrbitalElements], list[dict[str, Any]]]:
    valid_elements: list[OrbitalElements] = []
    failures: list[dict[str, Any]] = []
    for element, satrec, _fields in records:
        try:
            propagate(element, start, satrec=satrec)
            valid_elements.append(element)
        except (TypeError, ValueError, RuntimeError) as exc:
            failures.append({
                "catalog_number": int(element.catalog_number),
                "name": element.name,
                "error": str(exc),
            })
    return valid_elements, failures


@app.get("/conjunctions/scan")
@app.post("/conjunctions/scan")
def conjunction_scan(
    group: str = Query(default="tracked"),
    duration_minutes: int = Query(default=90),
    step_seconds: Optional[int] = Query(default=None),
    coarse_step_seconds: Optional[int] = Query(default=None),
    threshold_km: Optional[float] = Query(default=None),
    screening_distance_km: Optional[float] = Query(default=None),
    max_objects: int = Query(default=250),
    max_events: int = Query(default=25),
):
    resolved_step_seconds = step_seconds if step_seconds is not None else coarse_step_seconds if coarse_step_seconds is not None else 60
    resolved_threshold_km = threshold_km if threshold_km is not None else screening_distance_km if screening_distance_km is not None else 10.0

    if duration_minutes <= 0 or duration_minutes > 720:
        raise HTTPException(status_code=400, detail="duration_minutes must be between 1 and 720")
    if resolved_step_seconds <= 0 or resolved_step_seconds > 3600:
        raise HTTPException(status_code=400, detail="step_seconds must be between 1 and 3600")
    if resolved_threshold_km <= 0:
        raise HTTPException(status_code=400, detail="threshold_km must be positive")
    if max_objects <= 0:
        raise HTTPException(status_code=400, detail="max_objects must be positive")

    try:
        records = _load_group_records(group=group, max_objects=max_objects)
    except (CelesTrakError, ValueError, RuntimeError):
        cached = _cached_records(group, limit=max_objects)
        if not cached:
            raise HTTPException(status_code=503, detail=f"No cached data for group {group!r} and CelesTrak is unavailable")
        records = cached

    started_at = _utc_now()
    valid_elements, propagation_failures = _prepare_screening_objects(records, start=started_at)
    if len(valid_elements) < 2:
        return {
            "status": "ok",
            "objects_screened": len(valid_elements),
            "pairs_checked": 0,
            "threshold_km": resolved_threshold_km,
            "duration_minutes": duration_minutes,
            "step_seconds": resolved_step_seconds,
            "conjunctions": [],
            "events": [],
            "propagation_failures": propagation_failures,
            "candidate_pairs": 0,
        }

    satrecs = {item[0].catalog_number: item[1] for item in records if item[1] is not None and item[0].catalog_number in {el.catalog_number for el in valid_elements}}
    cfg = ScanConfig(
        duration_minutes=duration_minutes,
        coarse_step_seconds=resolved_step_seconds,
        screening_distance_km=resolved_threshold_km,
        max_relative_speed_bound_km_s=20.0,
        max_objects=max_objects,
        max_events=max_events,
    )
    candidate_pairs = _candidate_pairs(valid_elements, started_at, cfg, satrecs=satrecs)
    events = scan_conjunctions(valid_elements, start=started_at, config=cfg, satrecs=satrecs)

    run_id = create_scan_run(
        started_at=started_at,
        completed_at=_utc_now(),
        source_group=group,
        objects_loaded=len(valid_elements),
        duration_minutes=duration_minutes,
        coarse_step_seconds=resolved_step_seconds,
        screening_distance_km=resolved_threshold_km,
        events_found=len(events),
    )
    save_conjunction_observations(run_id, started_at, events)

    payload_events = []
    for event in events:
        rows = list_pair_history(event.object_a_catalog_number, event.object_b_catalog_number, limit=2)
        previous = None
        if rows:
            previous = {"risk_score": float(rows[-1]["risk_score"]), "miss_distance_km": float(rows[-1]["miss_distance_km"])}
        payload_events.append(
            _serialize_event(
                event,
                now=started_at,
                trend=_classify_trend({"risk_score": float(event.risk_score), "miss_distance_km": float(event.miss_distance_km)}, previous),
                data_age_minutes=0.0,
            )
        )

    return {
        "status": "ok",
        "scan_id": run_id,
        "objects_screened": len(valid_elements),
        "objects_scanned": len(valid_elements),
        "pairs_checked": len(candidate_pairs),
        "candidate_pairs": len(candidate_pairs),
        "threshold_km": resolved_threshold_km,
        "duration_minutes": duration_minutes,
        "step_seconds": resolved_step_seconds,
        "conjunctions": payload_events,
        "events": payload_events,
        "propagation_failures": propagation_failures,
    }


@app.get("/conjunctions/pair")
def conjunction_pair(catalog_a: int, catalog_b: int, duration_minutes: int = 120, step_seconds: int = 30):
    a, sat_a, _ = fetch_omm_by_catalog_number(_normalize_catalog(catalog_a))
    b, sat_b, _ = fetch_omm_by_catalog_number(_normalize_catalog(catalog_b))
    result = find_closest_approach(a, b, _utc_now(), duration_minutes, step_seconds, sat_a=sat_a, sat_b=sat_b)
    return _serialize_event(result, now=_utc_now())


@app.get("/conjunctions/history")
def conjunction_history(catalog_a: Union[str, int], catalog_b: Union[str, int], limit: int = 30):
    if limit <= 0 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    catalog_a_int = _normalize_catalog(catalog_a)
    catalog_b_int = _normalize_catalog(catalog_b)
    rows = list_pair_history(catalog_a_int, catalog_b_int, limit)
    observations = []
    for row in reversed(rows):
        observations.append(
            {
                "observation_id": row["id"],
                "run_id": row["run_id"],
                "observed_at": row["observed_at"],
                "tca": row["tca"],
                "miss_distance_km": round(float(row["miss_distance_km"]), 3),
                "relative_speed_km_s": round(float(row["relative_speed_km_s"]), 3),
                "risk_score": round(float(row["risk_score"]), 1),
                "risk_band": row["risk_band"],
            }
        )
    if len(observations) >= 2:
        latest = observations[-1]
        previous = observations[-2]
        trend = _classify_trend({"risk_score": latest["risk_score"], "miss_distance_km": latest["miss_distance_km"]}, {"risk_score": previous["risk_score"], "miss_distance_km": previous["miss_distance_km"]})
    else:
        trend = "NEW"
    return {"catalog_a": catalog_a_int, "catalog_b": catalog_b_int, "observations": observations, "trend": trend, "observation_count": len(observations)}


@app.get("/conjunctions/history/runs")
def scan_history(limit: int = 20):
    if limit <= 0 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return {"runs": [dict(row) for row in recent_scan_runs(limit)]}


@app.get("/conjunctions/history/analytics")
def conjunction_history_analytics():
    from .database.db import connect

    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM conjunction_observations ORDER BY observed_at DESC"
        ).fetchall()
        runs = conn.execute(
            "SELECT COUNT(*) AS run_count, COALESCE(SUM(events_found), 0) AS events_found, COALESCE(AVG(objects_loaded), 0) AS avg_objects, MAX(completed_at) AS latest_completed_at FROM scan_runs"
        ).fetchone()

    if not rows:
        return {
            "scan_runs": int(runs["run_count"] or 0),
            "stored_observations": 0,
            "mean_risk_score": 0.0,
            "minimum_miss_distance_km": None,
            "risk_distribution": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "trend_distribution": {"NEW": 0, "WORSENING": 0, "STABLE": 0, "IMPROVING": 0},
            "top_pairs": [],
        }

    bands = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    pair_counts: dict[str, dict[str, Any]] = {}
    scores = []
    miss_values = []
    for row in rows:
        band = str(row["risk_band"]).upper()
        if band in bands:
            bands[band] += 1
        scores.append(float(row["risk_score"]))
        miss_values.append(float(row["miss_distance_km"]))
        key = row["pair_key"]
        entry = pair_counts.setdefault(
            key,
            {
                "object_a": row["object_a_name"],
                "object_b": row["object_b_name"],
                "count": 0,
                "latest_risk": 0.0,
                "latest_miss_distance_km": float("inf"),
            },
        )
        entry["count"] += 1
        entry["latest_risk"] = max(entry["latest_risk"], float(row["risk_score"]))
        entry["latest_miss_distance_km"] = min(entry["latest_miss_distance_km"], float(row["miss_distance_km"]))

    trend_distribution = {"NEW": 0, "WORSENING": 0, "STABLE": 0, "IMPROVING": 0}
    for _, entry in pair_counts.items():
        if entry["latest_risk"] >= 75:
            trend_distribution["WORSENING"] += 1
        elif entry["latest_risk"] <= 25:
            trend_distribution["IMPROVING"] += 1
        else:
            trend_distribution["STABLE"] += 1

    if rows and len(rows) < 10:
        trend_distribution["NEW"] = min(1, len(rows))

    return {
        "scan_runs": int(runs["run_count"] or 0),
        "stored_observations": len(rows),
        "mean_risk_score": round(sum(scores) / len(scores), 1),
        "minimum_miss_distance_km": round(min(miss_values), 3) if miss_values else None,
        "risk_distribution": bands,
        "trend_distribution": trend_distribution,
        "top_pairs": [
            {
                "object_a": values["object_a"],
                "object_b": values["object_b"],
                "count": values["count"],
                "latest_risk": round(values["latest_risk"], 1),
                "latest_miss_distance_km": round(values["latest_miss_distance_km"], 3),
            }
            for _, values in sorted(pair_counts.items(), key=lambda item: item[1]["count"], reverse=True)[:10]
        ],
    }


@app.get("/conjunctions/visualization")
def conjunction_visualization(
    catalog_a: Union[str, int],
    catalog_b: Union[str, int],
    duration_minutes: int = 20,
    step_seconds: int = 30,
):
    if duration_minutes <= 0 or duration_minutes > 180:
        raise HTTPException(status_code=400, detail="duration_minutes must be between 1 and 180")
    if step_seconds <= 0 or step_seconds > 1800:
        raise HTTPException(status_code=400, detail="step_seconds must be between 1 and 1800")
    a, sat_a, _ = fetch_omm_by_catalog_number(_normalize_catalog(catalog_a))
    b, sat_b, _ = fetch_omm_by_catalog_number(_normalize_catalog(catalog_b))
    now = _utc_now()
    event = find_closest_approach(a, b, now, duration_minutes=max(60, duration_minutes), step_seconds=min(30, step_seconds), sat_a=sat_a, sat_b=sat_b)
    half_window = max(10, duration_minutes // 2)
    window_start = event.closest_approach - timedelta(minutes=half_window)
    samples_a = trajectory_window(a, window_start, duration_minutes, step_seconds, satrec=sat_a)
    samples_b = trajectory_window(b, window_start, duration_minutes, step_seconds, satrec=sat_b)
    state_a = propagate(a, event.closest_approach, satrec=sat_a)
    state_b = propagate(b, event.closest_approach, satrec=sat_b)

    def pointify(sample):
        x, y, z = teme_to_ecef(sample.x_km, sample.y_km, sample.z_km, sample.timestamp)
        lat, lon, alt = ecef_to_geodetic(x, y, z)
        return {
            "timestamp": sample.timestamp.isoformat(),
            "x_km": round(float(sample.x_km), 3),
            "y_km": round(float(sample.y_km), 3),
            "z_km": round(float(sample.z_km), 3),
            "ecef_x_km": round(float(x), 3),
            "ecef_y_km": round(float(y), 3),
            "ecef_z_km": round(float(z), 3),
            "lat_deg": round(float(lat), 4),
            "lon_deg": round(float(lon), 4),
            "alt_km": round(float(alt), 4),
        }

    return {
        "catalog_a": str(a.catalog_number),
        "catalog_b": str(b.catalog_number),
        "frame": "TEME",
        "tca": event.closest_approach.isoformat(),
        "miss_distance_km": round(float(event.miss_distance_km), 3),
        "relative_velocity_km_s": round(float(event.relative_speed_km_s), 3),
        "trajectory_a": [pointify(sample) for sample in samples_a],
        "trajectory_b": [pointify(sample) for sample in samples_b],
        "tca_position_a": {"x_km": round(float(state_a.x_km), 3), "y_km": round(float(state_a.y_km), 3), "z_km": round(float(state_a.z_km), 3)},
        "tca_position_b": {"x_km": round(float(state_b.x_km), 3), "y_km": round(float(state_b.y_km), 3), "z_km": round(float(state_b.z_km), 3)},
    }


@app.get("/visualization/multi")
def visualization_multi(catalog_numbers: str, duration_minutes: int = 180, step_seconds: int = 60):
    if duration_minutes <= 0 or duration_minutes > 720:
        raise HTTPException(status_code=400, detail="duration_minutes must be between 1 and 720")
    if step_seconds <= 0 or step_seconds > 3600:
        raise HTTPException(status_code=400, detail="step_seconds must be between 1 and 3600")
    ids = [int(part.strip()) for part in catalog_numbers.split(",") if part.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="catalog_numbers must not be empty")
    objects = []
    start = _utc_now()
    for catalog_number in ids[:50]:
        try:
            element, sat, _ = fetch_omm_by_catalog_number(catalog_number)
        except (CelesTrakError, ValueError, RuntimeError):
            continue
        trajectory = []
        for sample in propagate_forward(element, start, duration_minutes, step_seconds, satrec=sat):
            x, y, z = teme_to_ecef(sample.x_km, sample.y_km, sample.z_km, sample.timestamp)
            lat, lon, alt = ecef_to_geodetic(x, y, z)
            trajectory.append(
                {
                    "timestamp": sample.timestamp.isoformat(),
                    "x_km": round(float(x), 3),
                    "y_km": round(float(y), 3),
                    "z_km": round(float(z), 3),
                    "lat_deg": round(float(lat), 4),
                    "lon_deg": round(float(lon), 4),
                    "alt_km": round(float(alt), 4),
                }
            )
        objects.append({"catalog_number": str(catalog_number), "name": element.name, "trajectory": trajectory})
    return {"frame": "ECEF/PEF_APPROX", "objects": objects}


@app.get("/satellites/{catalog_number}")
def satellite_position(catalog_number: int, minutes_from_now: int = 0):
    if minutes_from_now < -10000 or minutes_from_now > 10000:
        raise HTTPException(status_code=400, detail="minutes_from_now is out of range")
    element, sat, _ = fetch_omm_by_catalog_number(_normalize_catalog(catalog_number))
    target = _utc_now() + timedelta(minutes=minutes_from_now)
    sample = propagate(element, target, satrec=sat)
    return {
        "name": element.name,
        "catalog_number": str(element.catalog_number),
        "timestamp": sample.timestamp.isoformat(),
        "frame": "TEME",
        "position_km": {"x": sample.x_km, "y": sample.y_km, "z": sample.z_km},
        "velocity_km_s": {"x": sample.vx_km_s, "y": sample.vy_km_s, "z": sample.vz_km_s},
    }


@app.get("/satellites/{catalog_number}/trajectory")
def satellite_trajectory(catalog_number: int, duration_minutes: int = 180, step_seconds: int = 120):
    if duration_minutes <= 0 or duration_minutes > 720:
        raise HTTPException(status_code=400, detail="duration_minutes must be between 1 and 720")
    if step_seconds <= 0 or step_seconds > 3600:
        raise HTTPException(status_code=400, detail="step_seconds must be between 1 and 3600")
    element, sat, _ = fetch_omm_by_catalog_number(_normalize_catalog(catalog_number))
    start = _utc_now().replace(microsecond=0)
    samples = propagate_forward(element, start, duration_minutes, step_seconds, satrec=sat)
    return {
        "name": element.name,
        "catalog_number": str(element.catalog_number),
        "frame": "TEME",
        "start": start.isoformat(),
        "duration_minutes": duration_minutes,
        "step_seconds": step_seconds,
        "points": [
            {"timestamp": sample.timestamp.isoformat(), "x_km": sample.x_km, "y_km": sample.y_km, "z_km": sample.z_km}
            for sample in samples
        ],
    }


@app.get("/satellites/{catalog_number}/earth-fixed-trajectory")
def earth_fixed_trajectory(catalog_number: int, duration_minutes: int = 180, step_seconds: int = 120):
    if duration_minutes <= 0 or duration_minutes > 720:
        raise HTTPException(status_code=400, detail="duration_minutes must be between 1 and 720")
    if step_seconds <= 0 or step_seconds > 3600:
        raise HTTPException(status_code=400, detail="step_seconds must be between 1 and 3600")
    element, sat, _ = fetch_omm_by_catalog_number(_normalize_catalog(catalog_number))
    start = _utc_now().replace(microsecond=0)
    samples = propagate_forward(element, start, duration_minutes, step_seconds, satrec=sat)
    points = []
    for sample in samples:
        x, y, z = teme_to_ecef(sample.x_km, sample.y_km, sample.z_km, sample.timestamp)
        lat, lon, alt = ecef_to_geodetic(x, y, z)
        points.append(
            {
                "timestamp": sample.timestamp.isoformat(),
                "x_km": round(float(x), 3),
                "y_km": round(float(y), 3),
                "z_km": round(float(z), 3),
                "lat_deg": round(float(lat), 4),
                "lon_deg": round(float(lon), 4),
                "alt_km": round(float(alt), 4),
            }
        )
    return {"name": element.name, "catalog_number": str(element.catalog_number), "frame": "ECEF/PEF_APPROX", "points": points}


@app.get("/data/health")
def data_health():
    return {"status": "ok", "message": "Dataset ready"}
