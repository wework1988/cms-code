"""User-confirmed spellings. Model guesses are never written here."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .catalog import CATALOG_DIR
from .geo import normalize_name

ALIAS_PATH = CATALOG_DIR / "confirmed-aliases.sqlite"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AliasStore:
    def __init__(self, path: Path | None = None):
        self.path = path or ALIAS_PATH

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS confirmed_alias (
              id INTEGER PRIMARY KEY,
              normalized TEXT NOT NULL,
              place_id TEXT NOT NULL,
              feature_type TEXT,
              level TEXT,
              country_code TEXT,
              state_place_id TEXT,
              district_place_id TEXT,
              catalogue_version TEXT,
              uid INTEGER,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_confirmed_alias_norm ON confirmed_alias(normalized, active)"
        )
        return conn

    def remember(self, record: dict) -> int:
        normalized = normalize_name(str(record.get("normalized") or record.get("name") or ""))
        place_id = str(record.get("place_id") or "")
        state_id = record.get("state_place_id") or None
        district_id = record.get("district_place_id") or None
        if len(normalized) < 2 or not place_id:
            raise ValueError("A remembered spelling needs a name and a catalogue place.")
        if not state_id and not district_id:
            raise ValueError("A remembered spelling needs a state or district so it cannot match every place with that name.")
        now = _now()
        conn = self._connect()
        try:
            existing = conn.execute(
                """
                SELECT id FROM confirmed_alias
                WHERE normalized=? AND place_id=? AND ifnull(state_place_id,'')=? AND ifnull(district_place_id,'')=?
                """,
                (normalized, place_id, state_id or "", district_id or ""),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE confirmed_alias
                    SET active=1, feature_type=?, level=?, country_code=?, catalogue_version=?, uid=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        record.get("feature_type"),
                        record.get("level"),
                        record.get("country_code"),
                        record.get("catalogue_version"),
                        record.get("uid"),
                        now,
                        existing["id"],
                    ),
                )
                conn.commit()
                return int(existing["id"])
            cursor = conn.execute(
                """
                INSERT INTO confirmed_alias (
                  normalized, place_id, feature_type, level, country_code, state_place_id,
                  district_place_id, catalogue_version, uid, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    normalized,
                    place_id,
                    record.get("feature_type"),
                    record.get("level"),
                    record.get("country_code"),
                    state_id,
                    district_id,
                    record.get("catalogue_version"),
                    record.get("uid"),
                    now,
                    now,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def match(self, name: str, context: dict) -> dict | None:
        """Return one compatible alias, or None when context is missing or several rows fit."""
        normalized = normalize_name(name)
        if len(normalized) < 2:
            return None
        state_ids = _context_ids(context, "state")
        district_ids = _context_ids(context, "district")
        if not state_ids and not district_ids:
            return None
        conn = self._connect()
        try:
            rows = list(conn.execute(
                "SELECT * FROM confirmed_alias WHERE normalized=? AND active=1",
                (normalized,),
            ))
        finally:
            conn.close()
        verified = context.get("verified") or {}
        expected_country = context.get("country_code") if verified.get("country") else None
        compatible = []
        for row in rows:
            if expected_country and row["country_code"] and row["country_code"] != expected_country:
                continue
            state_ok = not row["state_place_id"] or row["state_place_id"] in state_ids
            district_ok = not row["district_place_id"] or row["district_place_id"] in district_ids
            if row["state_place_id"] or row["district_place_id"]:
                if state_ok and district_ok:
                    compatible.append(dict(row))
        if len(compatible) != 1:
            return None
        return compatible[0]

    def list_rows(self) -> list[dict]:
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute("SELECT * FROM confirmed_alias ORDER BY updated_at DESC, id DESC")]
        finally:
            conn.close()

    def set_active(self, alias_id: int, active: bool) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE confirmed_alias SET active=?, updated_at=? WHERE id=?",
                (1 if active else 0, _now(), alias_id),
            )
            conn.commit()
        finally:
            conn.close()

    def remove(self, alias_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM confirmed_alias WHERE id=?", (alias_id,))
            conn.commit()
        finally:
            conn.close()


def _context_ids(context: dict, level: str) -> set[str]:
    found = set()
    parent = context.get("parent_entity") or {}
    if parent.get("level") == level and parent.get("id"):
        found.add(parent["id"])
    key = "state_id" if level == "state" else "district_id"
    if context.get(key):
        found.add(context[key])
    verified = context.get("verified") or {}
    if level == "state" and verified.get("state") and context.get("state_id"):
        found.add(context["state_id"])
    if level == "district" and verified.get("district") and context.get("district_id"):
        found.add(context["district_id"])
    return found
