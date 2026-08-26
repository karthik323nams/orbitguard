from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from ..models.orbital import OrbitalElements

import os

_env_db_path = os.getenv("ORBITGUARD_DB_PATH")
DB_PATH = (
    Path(_env_db_path)
    if _env_db_path
    else Path(__file__).resolve().parents[3] / "data" / "orbitguard.db"
)


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema_columns(conn: sqlite3.Connection) -> None:
    table_info = conn.execute("PRAGMA table_info(orbital_elements)").fetchall()
    existing = {str(row[1]) for row in table_info}
    for name, ddl in {
        "last_successful_fetch": "TEXT",
        "cache_fresh": "INTEGER NOT NULL DEFAULT 0",
        "stale_after_seconds": "INTEGER NOT NULL DEFAULT 7200",
    }.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE orbital_elements ADD COLUMN {name} {ddl}")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS orbital_elements (
                catalog_number INTEGER PRIMARY KEY,
                object_name TEXT NOT NULL,
                line1 TEXT,
                line2 TEXT,
                source_format TEXT NOT NULL,
                source_group TEXT,
                epoch TEXT,
                raw_json TEXT,
                fetched_at TEXT NOT NULL,
                last_successful_fetch TEXT,
                cache_fresh INTEGER NOT NULL DEFAULT 0,
                stale_after_seconds INTEGER NOT NULL DEFAULT 7200
            );
            CREATE INDEX IF NOT EXISTS idx_orbital_name ON orbital_elements(object_name);
            CREATE INDEX IF NOT EXISTS idx_orbital_group ON orbital_elements(source_group);

            CREATE TABLE IF NOT EXISTS satellite_launch_metadata (
                catalog_number INTEGER PRIMARY KEY,
                cospar_id TEXT,
                launch_date TEXT,
                launch_site_code TEXT,
                launch_site_name TEXT,
                owner_code TEXT,
                owner_name TEXT,
                launch_vehicle TEXT,
                fetched_at TEXT NOT NULL
            );
            """
        )
        _ensure_schema_columns(conn)


def upsert_elements(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO orbital_elements(
                catalog_number, object_name, line1, line2, source_format,
                source_group, epoch, raw_json, fetched_at,
                last_successful_fetch, cache_fresh, stale_after_seconds
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(catalog_number) DO UPDATE SET
                object_name=excluded.object_name,
                line1=excluded.line1,
                line2=excluded.line2,
                source_format=excluded.source_format,
                source_group=excluded.source_group,
                epoch=excluded.epoch,
                raw_json=excluded.raw_json,
                fetched_at=excluded.fetched_at,
                last_successful_fetch=excluded.last_successful_fetch,
                cache_fresh=excluded.cache_fresh,
                stale_after_seconds=excluded.stale_after_seconds
            """,
            [
                (
                    r["catalog_number"], r["object_name"], r.get("line1"), r.get("line2"),
                    r["source_format"], r.get("source_group"), r.get("epoch"),
                    r.get("raw_json"), r["fetched_at"], r.get("last_successful_fetch") or r["fetched_at"],
                    int(bool(r.get("cache_fresh", True))), int(r.get("stale_after_seconds", 7200)),
                ) for r in rows
            ],
        )
    return len(rows)


def list_elements(group: Optional[str] = None, limit: int = 100) -> list[sqlite3.Row]:
    with connect() as conn:
        if group:
            return conn.execute(
                "SELECT * FROM orbital_elements WHERE source_group=? ORDER BY catalog_number LIMIT ?",
                (group, limit),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM orbital_elements ORDER BY catalog_number LIMIT ?", (limit,)
        ).fetchall()


def get_launch_metadata(catalog_number: int) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM satellite_launch_metadata WHERE catalog_number=?", (catalog_number,)
        ).fetchone()
        if row:
            return dict(row)
    return None


def save_launch_metadata(m: dict) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO satellite_launch_metadata (
                catalog_number, cospar_id, launch_date, launch_site_code,
                launch_site_name, owner_code, owner_name, launch_vehicle, fetched_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(catalog_number) DO UPDATE SET
                cospar_id=excluded.cospar_id,
                launch_date=excluded.launch_date,
                launch_site_code=excluded.launch_site_code,
                launch_site_name=excluded.launch_site_name,
                owner_code=excluded.owner_code,
                owner_name=excluded.owner_name,
                launch_vehicle=excluded.launch_vehicle,
                fetched_at=excluded.fetched_at
            """,
            (
                m["catalog_number"], m.get("cospar_id"), m.get("launch_date"),
                m.get("launch_site_code"), m.get("launch_site_name"),
                m.get("owner_code"), m.get("owner_name"), m.get("launch_vehicle"),
                m["fetched_at"]
            )
        )

