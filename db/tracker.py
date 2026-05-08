"""
db/tracker.py — SQLite-backed application log.

Tracks every job application with:
  company, role, date, platform, status, job_url
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DB_PATH = Path("db") / "applications.db"


class ApplicationTracker:
    """Thread-safe SQLite wrapper for application tracking."""

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    # ──────────────────────────────────
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    company     TEXT    NOT NULL,
                    role        TEXT    NOT NULL,
                    platform    TEXT    NOT NULL,
                    job_url     TEXT    DEFAULT '',
                    status      TEXT    DEFAULT 'Applied',
                    applied_at  TEXT    NOT NULL,
                    notes       TEXT    DEFAULT ''
                )
                """
            )
            conn.commit()

    # ──────────────────────────────────
    def log(
        self,
        company: str,
        role: str,
        platform: str,
        job_url: str = "",
        status: str = "Applied",
        notes: str = "",
    ) -> int:
        """Insert a new application record. Returns its row id."""
        applied_at = datetime.now().isoformat(timespec="seconds")
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO applications (company, role, platform, job_url, status, applied_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (company, role, platform, job_url, status, applied_at, notes),
            )
            conn.commit()
            return cur.lastrowid

    def update_status(self, app_id: int, status: str):
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE applications SET status = ? WHERE id = ?",
                (status, app_id),
            )
            conn.commit()

    def get_all(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY applied_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_platform(self, platform: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM applications WHERE platform = ? ORDER BY applied_at DESC",
                (platform,),
            ).fetchall()
        return [dict(r) for r in rows]

    def already_applied(self, company: str, role: str, platform: str) -> bool:
        """Prevent duplicate applications."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM applications WHERE company=? AND role=? AND platform=?",
                (company, role, platform),
            ).fetchone()
        return row is not None
