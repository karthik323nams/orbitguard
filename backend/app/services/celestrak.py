from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from ..config import get_tracked_catalog_numbers
from ..models.orbital import OrbitalElements
from .omm import parse_omm_json

BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"
TIMEOUT_SECONDS = 30
CACHE_MAX_AGE_SECONDS = 2 * 60 * 60


class CelesTrakError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


def get_tracked_catalogs() -> list[int]:
    return get_tracked_catalog_numbers()


def validate_omm_record(fields: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(fields, dict):
        raise ValueError("OMM record must be a JSON object.")

    missing_required = [
        key for key in ("NORAD_CAT_ID", "OBJECT_NAME", "EPOCH")
        if fields.get(key) in (None, "")
    ]
    if missing_required:
        raise ValueError(f"OMM record missing required fields: {', '.join(missing_required)}")

    catalog_number = int(str(fields["NORAD_CAT_ID"]).strip())
    if catalog_number <= 0:
        raise ValueError(f"OMM record has invalid NORAD_CAT_ID: {fields['NORAD_CAT_ID']!r}")

    name = str(fields["OBJECT_NAME"]).strip()
    if not name:
        raise ValueError("OMM record has blank OBJECT_NAME")

    allowed_orbital = (
        "MEAN_MOTION",
        "ECCENTRICITY",
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER",
        "MEAN_ANOMALY",
        "BSTAR",
    )
    if not any(fields.get(key) not in (None, "") for key in allowed_orbital):
        raise ValueError("OMM record is missing orbital-element fields required for SGP4 initialization.")

    try:
        datetime.fromisoformat(str(fields["EPOCH"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"OMM record has invalid EPOCH: {fields['EPOCH']!r}") from exc

    return {
        "NORAD_CAT_ID": catalog_number,
        "OBJECT_NAME": name,
        "OBJECT_ID": fields.get("OBJECT_ID") or name,
        "EPOCH": str(fields["EPOCH"]),
        **{key: fields.get(key) for key in allowed_orbital if key in fields},
    }


def _catalog_from_tle(line1: str) -> int:
    raw = line1[2:7].strip()
    if not raw.isdigit():
        raise ValueError(f"Invalid TLE catalog number: {raw!r}")
    return int(raw)


def parse_tle_lines(text: str) -> list[OrbitalElements]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    results: list[OrbitalElements] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("1 ") and i + 1 < len(lines) and lines[i + 1].startswith("2 "):
            line1, line2 = lines[i], lines[i + 1]
            catalog = _catalog_from_tle(line1)
            results.append(OrbitalElements(name=f"CATALOG {catalog}", catalog_number=catalog, line1=line1, line2=line2))
            i += 2
            continue
        if i + 2 < len(lines) and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            name = re.sub(r"\s+", " ", lines[i]).strip()
            line1, line2 = lines[i + 1], lines[i + 2]
            catalog = _catalog_from_tle(line1)
            results.append(OrbitalElements(name=name, catalog_number=catalog, line1=line1, line2=line2))
            i += 3
            continue
        i += 1
    if not results:
        raise CelesTrakError("No valid TLE records were found in the CelesTrak response.")
    return results


def _request(params: dict[str, Any]) -> requests.Response:
    url = f"{BASE_URL}?{urlencode(params)}"
    headers = {"User-Agent": "Astrail/1.0", "Accept": "application/json"}
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS, headers=headers)
    except requests.RequestException as exc:
        raise CelesTrakError(f"CelesTrak request failed: {exc}") from exc

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = getattr(response, "status_code", None)
        body = (getattr(response, "text", "") or "")
        summary = re.sub(r"\s+", " ", body[:180]).strip() if body else "no response body"
        raise CelesTrakError(
            f"CelesTrak request failed with HTTP {status_code}: {summary or str(exc)}",
            status_code=status_code,
            response_text=body,
        ) from exc
    return response


def fetch_group_omm(group: str = "active", max_objects: Optional[int] = None):
    response = _request({"GROUP": group, "FORMAT": "JSON"})
    records = parse_omm_json(response.text, source_group=group)
    if max_objects is not None:
        records = records[:max_objects]
    return records


def fetch_group_tle(group: str = "active", max_objects: Optional[int] = None) -> list[OrbitalElements]:
    response = _request({"GROUP": group, "FORMAT": "TLE"})
    objects = parse_tle_lines(response.text)
    if max_objects is not None:
        objects = objects[:max_objects]
    return objects


def fetch_tle_by_catalog_number(catalog_number: int) -> OrbitalElements:
    response = _request({"CATNR": catalog_number, "FORMAT": "TLE"})
    objects = parse_tle_lines(response.text)
    for obj in objects:
        if obj.catalog_number == catalog_number:
            return obj
    raise CelesTrakError(f"Catalog number {catalog_number} was not returned by CelesTrak.")


def fetch_omm_by_catalog_number(catalog_number: int):
    response = _request({"CATNR": catalog_number, "FORMAT": "JSON"})
    records = parse_omm_json(response.text)
    for record in records:
        if record[0].catalog_number == catalog_number:
            return record
    raise CelesTrakError(f"Catalog number {catalog_number} was not returned by CelesTrak.")


def fetch_satcat_by_catalog_number(catalog_number: int) -> Optional[dict]:
    """
    Fetch SATCAT record for a single object catalog number.
    Returns parsed dictionary or None on error.
    """
    url = "https://celestrak.org/satcat/records.php"
    headers = {"User-Agent": "Astrail/1.0", "Accept": "application/json"}
    try:
        # Bypass custom _request helper here to avoid formatting issues and allow simple JSON handling
        resp = requests.get(url, params={"CATNR": catalog_number}, headers=headers, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
    except Exception:
        return None
    return None

