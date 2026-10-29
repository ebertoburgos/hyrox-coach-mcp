"""Local SQLite store: cached provider responses, session notes and the race profile."""

import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any


def _home() -> Path:
    env = os.getenv("HYROX_COACH_HOME") or os.getenv("HYBRID_COACH_HOME")  # old name still honoured
    if env:
        return Path(env).expanduser()
    home = Path("~/.hyrox-coach").expanduser()
    legacy = Path("~/.hybrid-coach").expanduser()
    if not home.exists() and legacy.exists():
        # Project was renamed: carry notes and race profile over (copy, never move).
        shutil.copytree(legacy, home)
    return home


HOME = _home()

SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, fetched_at REAL, body TEXT);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    activity_id INTEGER,
    text TEXT NOT NULL,
    stations TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS profile (key TEXT PRIMARY KEY, value TEXT);
"""


class Store:
    def __init__(self, path: Path | None = None):
        if path is None:
            HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = HOME / "coach.db"
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # --- cache ---
    def cached(self, key: str, ttl_s: float) -> Any | None:
        row = self.db.execute("SELECT fetched_at, body FROM cache WHERE key = ?", (key,)).fetchone()
        if row and time.time() - row["fetched_at"] < ttl_s:
            return json.loads(row["body"])
        return None

    def put(self, key: str, value: Any) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
            (key, time.time(), json.dumps(value, default=str)),
        )
        self.db.commit()

    # --- notes ---
    def add_note(self, date: str, text: str, stations: list[dict], activity_id: int | None) -> int:
        cur = self.db.execute(
            "INSERT INTO notes (date, activity_id, text, stations) VALUES (?, ?, ?, ?)",
            (date, activity_id, text, json.dumps(stations)),
        )
        self.db.commit()
        return cur.lastrowid

    def notes(self, since: str | None = None) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM notes WHERE date >= ? ORDER BY date, id", (since or "0000",)
        ).fetchall()
        return [{**dict(r), "stations": json.loads(r["stations"])} for r in rows]

    # --- profile ---
    def profile(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self.db.execute("SELECT key, value FROM profile")}

    def set_profile(self, **values: str | None) -> None:
        for k, v in values.items():
            if v is not None:
                self.db.execute("INSERT OR REPLACE INTO profile VALUES (?, ?)", (k, v))
        self.db.commit()
