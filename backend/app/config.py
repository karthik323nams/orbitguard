from __future__ import annotations

import os

# Default to a small but real multi-object CelesTrak catalog list so the tracked
# dataset is not artificially limited to the ISS. These are real catalog IDs from
# publicly available orbital element feeds and can be overridden with the
# ORBITGUARD_TRACKED_CATALOGS environment variable.
DEFAULT_TRACKED_CATALOGS = [25544, 22335, 24793, 42712, 43226, 44235, 40100]
DEFAULT_TRACKED_GROUP = "active"


def get_tracked_group() -> str:
    raw = os.getenv("ORBITGUARD_TRACKED_GROUP", DEFAULT_TRACKED_GROUP)
    value = (raw or DEFAULT_TRACKED_GROUP).strip()
    return value or DEFAULT_TRACKED_GROUP


def get_tracked_catalog_numbers() -> list[int]:
    raw = os.getenv("ORBITGUARD_TRACKED_CATALOGS")
    if raw is None or not raw.strip():
        return list(DEFAULT_TRACKED_CATALOGS)

    values: list[int] = []
    seen: set[int] = set()
    for token in raw.replace("\n", ",").split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        try:
            catalog_number = int(cleaned)
        except ValueError as exc:  # pragma: no cover - defensive config parsing
            raise ValueError(f"Invalid NORAD catalog list entry: {cleaned!r}") from exc
        if catalog_number <= 0:
            raise ValueError(f"Invalid NORAD catalog list entry: {cleaned!r}")
        if catalog_number not in seen:
            seen.add(catalog_number)
            values.append(catalog_number)

    return values or list(DEFAULT_TRACKED_CATALOGS)
