from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from .db import connect


def init_history_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                source_group TEXT NOT NULL,
                objects_loaded INTEGER NOT NULL,
                duration_minutes INTEGER NOT NULL,
                coarse_step_seconds INTEGER NOT NULL,
                screening_distance_km REAL NOT NULL,
                events_found INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_scan_runs_started ON scan_runs(started_at DESC);

            CREATE TABLE IF NOT EXISTS conjunction_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                pair_key TEXT NOT NULL,
                object_a_catalog_number INTEGER NOT NULL,
                object_b_catalog_number INTEGER NOT NULL,
                object_a_name TEXT NOT NULL,
                object_b_name TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                tca TEXT NOT NULL,
                miss_distance_km REAL NOT NULL,
                relative_speed_km_s REAL NOT NULL,
                risk_score REAL NOT NULL,
                risk_band TEXT NOT NULL,
                risk_breakdown_json TEXT,
                FOREIGN KEY(run_id) REFERENCES scan_runs(id)
            );
            CREATE INDEX IF NOT EXISTS idx_conj_pair_observed ON conjunction_observations(pair_key, observed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_conj_run ON conjunction_observations(run_id);
            """
        )


def create_scan_run(
    *,
    started_at: datetime,
    completed_at: datetime,
    source_group: str,
    objects_loaded: int,
    duration_minutes: int,
    coarse_step_seconds: int,
    screening_distance_km: float,
    events_found: int,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO scan_runs(
                started_at, completed_at, source_group, objects_loaded,
                duration_minutes, coarse_step_seconds, screening_distance_km, events_found
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                started_at.isoformat(), completed_at.isoformat(), source_group,
                objects_loaded, duration_minutes, coarse_step_seconds,
                screening_distance_km, events_found,
            ),
        )
        return int(cur.lastrowid)


def _pair_key(a: int, b: int) -> str:
    low, high = sorted((int(a), int(b)))
    return f"{low}:{high}"


def save_conjunction_observations(run_id: int, observed_at: datetime, events: Iterable) -> int:
    rows = []
    stamp = observed_at.astimezone(timezone.utc).isoformat()
    for event in events:
        rows.append(
            (
                run_id,
                _pair_key(event.object_a_catalog_number, event.object_b_catalog_number),
                event.object_a_catalog_number,
                event.object_b_catalog_number,
                event.object_a_name,
                event.object_b_name,
                stamp,
                event.closest_approach.isoformat(),
                event.miss_distance_km,
                event.relative_speed_km_s,
                event.risk_score,
                event.severity,
                json.dumps(event.risk_breakdown or {}),
            )
        )
    if not rows:
        return 0
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO conjunction_observations(
                run_id, pair_key, object_a_catalog_number, object_b_catalog_number,
                object_a_name, object_b_name, observed_at, tca, miss_distance_km,
                relative_speed_km_s, risk_score, risk_band, risk_breakdown_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
    return len(rows)


def list_pair_history(catalog_a: int, catalog_b: int, limit: int = 30) -> list[sqlite3.Row]:
    key = _pair_key(catalog_a, catalog_b)
    with connect() as conn:
        return conn.execute(
            """
            SELECT * FROM conjunction_observations
            WHERE pair_key=?
            ORDER BY observed_at DESC
            LIMIT ?
            """,
            (key, limit),
        ).fetchall()


def recent_scan_runs(limit: int = 20) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
