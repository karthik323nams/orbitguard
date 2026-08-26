from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional, Union

from sgp4.api import Satrec
from sgp4 import omm

from ..models.orbital import OrbitalElements


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


def _catalog_number(fields: dict[str, Any]) -> int:
    raw = fields.get("NORAD_CAT_ID") or fields.get("NORAD_CAT_ID")
    if raw is None:
        raise ValueError("OMM record has no NORAD_CAT_ID")
    return int(str(raw).strip())


def parse_omm_json(payload: Union[str, bytes], source_group: Optional[str] = None) -> list[tuple[OrbitalElements, Satrec, dict[str, Any]]]:
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("Expected CelesTrak JSON GP response to be a list of records")

    from .celestrak import validate_omm_record

    results = []
    for fields in data:
        if not isinstance(fields, dict):
            continue
        validate_omm_record(fields)
        normalized = dict(fields)
        epoch = _normalize_omm_epoch(normalized.get("EPOCH"))
        if epoch is not None:
            normalized["EPOCH"] = epoch
        sat = Satrec()
        omm.initialize(sat, normalized)
        catalog = _catalog_number(fields)
        name = str(fields.get("OBJECT_NAME") or f"CATALOG {catalog}").strip()
        epoch_raw = fields.get("EPOCH")
        epoch = None
        if epoch_raw:
            try:
                epoch = datetime.fromisoformat(str(epoch_raw).replace("Z", "+00:00"))
            except ValueError:
                epoch = None
        results.append((
            OrbitalElements(name=name, catalog_number=catalog, line1="", line2="", epoch=epoch),
            sat,
            fields,
        ))
    if not results:
        raise ValueError("No usable OMM records were found")
    return results
