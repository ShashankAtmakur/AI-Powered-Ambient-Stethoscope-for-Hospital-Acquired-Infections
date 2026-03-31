"""
backend/database.py
SQLite storage layer for the backend aggregator.

Uses only derived acoustic features – no audio waveforms or PII.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Generator, List, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import DB_PATH
from shared.schemas import RoomAlert, RoomEvent

logger = logging.getLogger(__name__)

# ── DDL ───────────────────────────────────────────────────────────────────────

_DDL_EVENTS = """
CREATE TABLE IF NOT EXISTS room_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id         TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    scenario        TEXT    NOT NULL DEFAULT 'normal',
    cough_detected  INTEGER NOT NULL DEFAULT 0,
    cough_confidence REAL   NOT NULL DEFAULT 0,
    coughs_per_min  REAL    NOT NULL DEFAULT 0,
    sneezes_per_min REAL    NOT NULL DEFAULT 0,
    snores_per_min  REAL    NOT NULL DEFAULT 0,
    wheeze_detected INTEGER NOT NULL DEFAULT 0,
    wheeze_confidence REAL  NOT NULL DEFAULT 0,
    breath_rate_bpm REAL    NOT NULL DEFAULT 14,
    breath_irregularity REAL NOT NULL DEFAULT 0,
    spo2_pct        REAL    NOT NULL DEFAULT 97.5,
    temperature_c   REAL    NOT NULL DEFAULT 37,
    ambient_noise_db REAL   NOT NULL DEFAULT 40,
    anomaly_label   TEXT    NOT NULL DEFAULT 'normal',
    anomaly_score   REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_room_ts ON room_events (room_id, timestamp);
"""

_DDL_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id         TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    alert_type      TEXT    NOT NULL,
    severity        TEXT    NOT NULL,
    message         TEXT    NOT NULL,
    risk_score      REAL    NOT NULL DEFAULT 0,
    acknowledged    INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TEXT,
    acknowledged_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_room ON alerts (room_id, acknowledged);
"""


class Database:
    """Thin wrapper around SQLite for the backend aggregator."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_DDL_EVENTS)
            conn.executescript(_DDL_ALERTS)
            cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(room_events)").fetchall()
            }
            if "sneezes_per_min" not in cols:
                conn.execute(
                    "ALTER TABLE room_events ADD COLUMN sneezes_per_min REAL NOT NULL DEFAULT 0"
                )
            if "snores_per_min" not in cols:
                conn.execute(
                    "ALTER TABLE room_events ADD COLUMN snores_per_min REAL NOT NULL DEFAULT 0"
                )
        logger.info("Database initialised at %s", self.db_path)

    # ── Events ────────────────────────────────────────────────────────────────

    def insert_event(self, event: RoomEvent) -> None:
        sql = """
            INSERT INTO room_events
            (room_id, timestamp, scenario, cough_detected, cough_confidence,
             coughs_per_min, sneezes_per_min, snores_per_min,
             wheeze_detected, wheeze_confidence,
             breath_rate_bpm, breath_irregularity, spo2_pct,
             temperature_c, ambient_noise_db, anomaly_label, anomaly_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                event.room_id,
                event.timestamp.isoformat(),
                event.scenario.value,
                int(event.cough_detected),
                event.cough_confidence,
                event.coughs_per_min,
                event.sneezes_per_min,
                event.snores_per_min,
                int(event.wheeze_detected),
                event.wheeze_confidence,
                event.breath_rate_bpm,
                event.breath_irregularity,
                event.spo2_pct,
                event.temperature_c,
                event.ambient_noise_db,
                event.anomaly_label,
                event.anomaly_score,
            ))

    def get_recent_events(
        self, room_id: str, window_seconds: int = 300
    ) -> List[sqlite3.Row]:
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM room_events WHERE room_id=? AND timestamp>? "
                "ORDER BY timestamp DESC",
                (room_id, cutoff),
            )
            return cur.fetchall()

    def get_timeseries(
        self, room_id: str, limit: int = 120
    ) -> List[sqlite3.Row]:
        """Return the most recent *limit* rows for a room (for charts)."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM room_events WHERE room_id=? "
                "ORDER BY timestamp DESC LIMIT ?",
                (room_id, limit),
            )
            rows = cur.fetchall()
        return list(reversed(rows))

    # ── Alerts ────────────────────────────────────────────────────────────────

    def insert_alert(self, alert: RoomAlert) -> int:
        sql = """
            INSERT INTO alerts
            (room_id, timestamp, alert_type, severity, message,
             risk_score, acknowledged)
            VALUES (?,?,?,?,?,?,0)
        """
        with self._connect() as conn:
            cur = conn.execute(sql, (
                alert.room_id,
                alert.timestamp.isoformat(),
                alert.alert_type.value,
                alert.severity.value,
                alert.message,
                alert.risk_score,
            ))
            return cur.lastrowid  # type: ignore[return-value]

    def get_active_alerts(self, room_id: Optional[str] = None) -> List[sqlite3.Row]:
        if room_id:
            sql = ("SELECT * FROM alerts WHERE acknowledged=0 AND room_id=? "
                   "ORDER BY timestamp DESC")
            args = (room_id,)
        else:
            sql = "SELECT * FROM alerts WHERE acknowledged=0 ORDER BY timestamp DESC"
            args = ()
        with self._connect() as conn:
            return conn.execute(sql, args).fetchall()

    def acknowledge_alert(
        self,
        alert_id: int,
        acknowledged_by: str = "nurse",
    ) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE alerts SET acknowledged=1, acknowledged_at=?, "
                "acknowledged_by=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), acknowledged_by, alert_id),
            )
            return cur.rowcount > 0

    def get_all_alerts(self, limit: int = 200) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
